from datetime import datetime, timedelta
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select, func

from app.core.database import get_session
from app.models.profile import UserProfessionalInfo
from app.models.refresh_token import RefreshToken
from app.models.user_extended import Usuario, TipoSexo
from app.routers.auth import get_current_active_user

router = APIRouter(prefix="/profile", tags=["profile"])


class ProfessionalInfo(BaseModel):
    puesto: Optional[str] = Field(default=None, max_length=100)
    departamento: Optional[str] = Field(default=None, max_length=100)
    fecha_ingreso: Optional[str] = None
    id_empleado: Optional[str] = Field(default=None, max_length=50)


class ProfileStats(BaseModel):
    sessions: int
    activity: str
    reports: int


class ProfileMeResponse(BaseModel):
    id: int
    nombres: str
    apellidos: str
    email: Optional[str]
    telefono: Optional[str]
    direccion: Optional[str]
    sexo: Optional[str]
    fecha_nac: Optional[str]
    fecha_creacion: str
    roles: List[str]
    professional: ProfessionalInfo
    stats: ProfileStats


class ProfileMeUpdateRequest(BaseModel):
    nombres: str = Field(min_length=1, max_length=100)
    apellidos: str = Field(min_length=1, max_length=100)
    telefono: Optional[str] = Field(default=None, max_length=20)
    direccion: Optional[str] = Field(default=None, max_length=255)

    puesto: Optional[str] = Field(default=None, max_length=100)
    departamento: Optional[str] = Field(default=None, max_length=100)
    fecha_ingreso: Optional[str] = None
    id_empleado: Optional[str] = Field(default=None, max_length=50)


def _get_or_create_professional(session: Session, user_id: int) -> UserProfessionalInfo:
    record = session.exec(select(UserProfessionalInfo).where(UserProfessionalInfo.user_id == user_id)).first()
    if record:
        return record
    record = UserProfessionalInfo(user_id=user_id)
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def _activity_from_last_login(last_login: Optional[datetime]) -> str:
    if not last_login:
        return "Bajo"
    now = datetime.utcnow()
    if last_login >= now - timedelta(days=1):
        return "Alto"
    if last_login >= now - timedelta(days=7):
        return "Medio"
    return "Bajo"


def _role_names(user: Usuario) -> List[str]:
    try:
        return [ur.rol.tipo for ur in (user.roles or []) if ur.rol and ur.rol.tipo] or ["Sin rol"]
    except Exception:
        return ["Sin rol"]


@router.get("/me", response_model=ProfileMeResponse)
def get_profile_me(
    current_user: Annotated[Usuario, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
):
    professional = _get_or_create_professional(session, current_user.id)

    sessions_count = session.exec(
        select(func.count(RefreshToken.id)).where(RefreshToken.user_id == current_user.id)
    ).one()

    sexo = current_user.sexo.value if isinstance(current_user.sexo, TipoSexo) else (current_user.sexo or None)

    return ProfileMeResponse(
        id=current_user.id,
        nombres=current_user.nombres,
        apellidos=current_user.apellidos,
        email=current_user.email,
        telefono=current_user.telefono,
        direccion=current_user.direccion,
        sexo=sexo,
        fecha_nac=current_user.fecha_nac.isoformat() if current_user.fecha_nac else None,
        fecha_creacion=current_user.fecha_creacion.isoformat(),
        roles=_role_names(current_user),
        professional=ProfessionalInfo(
            puesto=professional.puesto,
            departamento=professional.departamento,
            fecha_ingreso=professional.fecha_ingreso.isoformat() if professional.fecha_ingreso else None,
            id_empleado=professional.id_empleado,
        ),
        stats=ProfileStats(
            sessions=int(sessions_count or 0),
            activity=_activity_from_last_login(current_user.ultimo_login),
            reports=0,
        ),
    )


@router.put("/me", response_model=ProfileMeResponse)
def update_profile_me(
    payload: ProfileMeUpdateRequest,
    current_user: Annotated[Usuario, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
):
    current_user.nombres = payload.nombres
    current_user.apellidos = payload.apellidos
    current_user.telefono = payload.telefono
    current_user.direccion = payload.direccion

    professional = _get_or_create_professional(session, current_user.id)
    professional.puesto = payload.puesto
    professional.departamento = payload.departamento
    professional.id_empleado = payload.id_empleado
    professional.updated_at = datetime.utcnow()

    if payload.fecha_ingreso:
        try:
            professional.fecha_ingreso = datetime.fromisoformat(payload.fecha_ingreso).date()
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Fecha de ingreso inválida")
    else:
        professional.fecha_ingreso = None

    session.add(current_user)
    session.add(professional)
    session.commit()
    session.refresh(current_user)
    session.refresh(professional)

    sessions_count = session.exec(
        select(func.count(RefreshToken.id)).where(RefreshToken.user_id == current_user.id)
    ).one()
    sexo = current_user.sexo.value if isinstance(current_user.sexo, TipoSexo) else (current_user.sexo or None)

    return ProfileMeResponse(
        id=current_user.id,
        nombres=current_user.nombres,
        apellidos=current_user.apellidos,
        email=current_user.email,
        telefono=current_user.telefono,
        direccion=current_user.direccion,
        sexo=sexo,
        fecha_nac=current_user.fecha_nac.isoformat() if current_user.fecha_nac else None,
        fecha_creacion=current_user.fecha_creacion.isoformat(),
        roles=_role_names(current_user),
        professional=ProfessionalInfo(
            puesto=professional.puesto,
            departamento=professional.departamento,
            fecha_ingreso=professional.fecha_ingreso.isoformat() if professional.fecha_ingreso else None,
            id_empleado=professional.id_empleado,
        ),
        stats=ProfileStats(
            sessions=int(sessions_count or 0),
            activity=_activity_from_last_login(current_user.ultimo_login),
            reports=0,
        ),
    )

