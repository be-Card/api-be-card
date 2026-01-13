"""
Router para configuración de usuario (settings)
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlmodel import Session, select
from typing import Annotated, List, Optional
from pydantic import BaseModel, Field

from app.core.database import get_session
from app.routers.auth import get_current_active_user
from app.models.user_extended import Usuario
from app.core.security import verify_password, get_password_hash
from app.core.rate_limit import limiter, PASSWORD_RATE_LIMIT
from app.models.settings import UserPreferencesDB
from app.models.refresh_token import RefreshToken

router = APIRouter(prefix="/settings", tags=["settings"])


class UserPreferences(BaseModel):
    """Preferencias de usuario"""
    notifications_email_sales: bool = True
    notifications_email_inventory: bool = True
    notifications_email_clients: bool = True
    notifications_push_critical: bool = True
    notifications_push_reports: bool = True
    language: str = Field(default="es", max_length=5)
    date_format: str = Field(default="YYYY-MM-DD", max_length=20)
    theme: str = Field(default="dark", max_length=20)


class ChangePasswordRequest(BaseModel):
    """Request para cambiar contraseña"""
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, description="Nueva contraseña (mínimo 8 caracteres)")


class UserPreferencesResponse(BaseModel):
    """Respuesta de preferencias"""
    user_id: int
    preferences: UserPreferences
    message: str


class ActiveSession(BaseModel):
    id: str
    device: str
    ip: str
    last_active: str
    location: str
    current: bool


class ActiveSessionsResponse(BaseModel):
    user_id: int
    sessions: List[ActiveSession]
    total: int


def _get_or_create_preferences(session: Session, user_id: int) -> UserPreferencesDB:
    record = session.exec(select(UserPreferencesDB).where(UserPreferencesDB.user_id == user_id)).first()
    if record:
        return record
    record = UserPreferencesDB(user_id=user_id)
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def _to_preferences(record: UserPreferencesDB) -> UserPreferences:
    return UserPreferences(
        notifications_email_sales=record.notifications_email_sales,
        notifications_email_inventory=record.notifications_email_inventory,
        notifications_email_clients=record.notifications_email_clients,
        notifications_push_critical=record.notifications_push_critical,
        notifications_push_reports=record.notifications_push_reports,
        language=record.language,
        date_format=record.date_format,
        theme=record.theme,
    )


def _parse_device(user_agent: Optional[str]) -> str:
    ua = (user_agent or "").lower()
    os_name = "Dispositivo"
    if "windows" in ua:
        os_name = "Windows"
    elif "mac os" in ua or "macintosh" in ua:
        os_name = "MacOS"
    elif "android" in ua:
        os_name = "Android"
    elif "iphone" in ua or "ios" in ua:
        os_name = "iOS"
    elif "linux" in ua:
        os_name = "Linux"

    browser = "Web"
    if "edg" in ua:
        browser = "Edge"
    elif "chrome" in ua and "chromium" not in ua:
        browser = "Chrome"
    elif "firefox" in ua:
        browser = "Firefox"
    elif "safari" in ua and "chrome" not in ua:
        browser = "Safari"
    return f"{browser} en {os_name}"


@router.get("/preferences", response_model=UserPreferencesResponse)
def get_user_preferences(
    current_user: Annotated[Usuario, Depends(get_current_active_user)],
    session: Session = Depends(get_session)
):
    """
    Obtener preferencias del usuario actual

    Retorna configuración de notificaciones, idioma, tema, etc.
    """
    record = _get_or_create_preferences(session, current_user.id)
    preferences = _to_preferences(record)

    return UserPreferencesResponse(
        user_id=current_user.id,
        preferences=preferences,
        message="Preferencias obtenidas exitosamente"
    )


@router.put("/preferences", response_model=UserPreferencesResponse)
def update_user_preferences(
    preferences: UserPreferences,
    current_user: Annotated[Usuario, Depends(get_current_active_user)],
    session: Session = Depends(get_session)
):
    """
    Actualizar preferencias del usuario actual

    Permite cambiar notificaciones, idioma, tema, formato de fecha, etc.
    """
    record = _get_or_create_preferences(session, current_user.id)
    record.notifications_email_sales = preferences.notifications_email_sales
    record.notifications_email_inventory = preferences.notifications_email_inventory
    record.notifications_email_clients = preferences.notifications_email_clients
    record.notifications_push_critical = preferences.notifications_push_critical
    record.notifications_push_reports = preferences.notifications_push_reports
    record.language = preferences.language
    record.date_format = preferences.date_format
    record.theme = preferences.theme
    record.updated_at = datetime.utcnow()
    session.add(record)
    session.commit()
    session.refresh(record)

    return UserPreferencesResponse(
        user_id=current_user.id,
        preferences=_to_preferences(record),
        message="Preferencias actualizadas exitosamente"
    )


@router.post("/change-password", response_model=dict)
@limiter.limit(PASSWORD_RATE_LIMIT)
def change_password(
    request: Request,
    password_data: ChangePasswordRequest,
    current_user: Annotated[Usuario, Depends(get_current_active_user)],
    session: Session = Depends(get_session)
):
    """
    Cambiar contraseña del usuario actual

    **Rate Limited**: Máximo 3 intentos por minuto para evitar brute force

    - **current_password**: Contraseña actual para verificar identidad
    - **new_password**: Nueva contraseña (debe cumplir requisitos de complejidad)
    """
    # Verificar contraseña actual
    if not verify_password(password_data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña actual es incorrecta"
        )

    # Verificar que la nueva contraseña sea diferente
    if password_data.current_password == password_data.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La nueva contraseña debe ser diferente a la actual"
        )

    # Actualizar contraseña
    try:
        new_password_hash = get_password_hash(password_data.new_password)
        current_user.password_hash = new_password_hash
        session.add(current_user)
        session.commit()

        return {
            "message": "Contraseña actualizada exitosamente",
            "user_id": current_user.id
        }

    except Exception:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al actualizar contraseña"
        )


@router.get("/active-sessions", response_model=ActiveSessionsResponse)
def get_active_sessions(
    current_user: Annotated[Usuario, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
):
    """
    Obtener sesiones activas del usuario
    """
    now = datetime.utcnow()
    records = session.exec(
        select(RefreshToken)
        .where(
            RefreshToken.user_id == current_user.id,
            RefreshToken.revoked_at == None,
            RefreshToken.expires_at > now,
        )
        .order_by(RefreshToken.issued_at.desc())
    ).all()

    sessions: List[ActiveSession] = []
    for idx, rec in enumerate(records):
        sessions.append(
            ActiveSession(
                id=str(rec.id),
                device=_parse_device(rec.user_agent),
                ip=rec.ip_address or "",
                last_active=rec.issued_at.isoformat(),
                location="—",
                current=idx == 0,
            )
        )

    return ActiveSessionsResponse(user_id=current_user.id, sessions=sessions, total=len(sessions))


@router.delete("/sessions/{session_id}")
def close_session(
    session_id: str,
    current_user: Annotated[Usuario, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
):
    """
    Cerrar sesión específica
    """
    try:
        token_id = int(session_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session ID inválido")

    record = session.get(RefreshToken, token_id)
    if record is None or record.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sesión no encontrada")

    if record.revoked_at is None:
        record.revoked_at = datetime.utcnow()
        session.add(record)
        session.commit()

    return {"message": "Sesión cerrada exitosamente", "user_id": current_user.id}
