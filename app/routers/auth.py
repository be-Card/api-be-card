"""
Router de autenticación - Refactorizado para usar Usuario
"""
from datetime import datetime, timedelta
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError

from app.core.database import get_session
from app.core.security import create_access_token, create_refresh_token, verify_token
from app.core.config import settings
from app.core.rate_limit import limiter, AUTH_RATE_LIMIT, PASSWORD_RATE_LIMIT, READ_RATE_LIMIT
from app.services.refresh_tokens import (
    compute_refresh_token_hash,
    get_refresh_token_by_hash,
    revoke_refresh_token,
    store_refresh_token,
)
from app.services.users import UserService
from app.services.password_reset import PasswordResetService
from app.services.email_verification import EmailVerificationService
from app.services.email_service import EmailService
from app.models.user_extended import Usuario, UsuarioRol, TipoRolUsuario
from app.schemas.auth import (
    Token,
    LoginJSONRequest,
    RefreshTokenRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
    ResendVerificationRequest,
)
from app.schemas.register import RegisterResponse
from app.schemas.users import UserCreate, UserRead, UserWithRoles, RolRead, TipoRolUsuarioRead

router = APIRouter(prefix="/auth", tags=["authentication"])

# OAuth2 scheme para extraer el token del header Authorization
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], 
    session: Session = Depends(get_session)
) -> Usuario:
    """Obtener usuario actual desde el token JWT"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = verify_token(token, expected_type="access")
    if payload is None:
        raise credentials_exception
    
    user_id_str = payload.get("sub")
    if user_id_str is None:
        raise credentials_exception
    
    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise credentials_exception
    
    user = session.get(Usuario, user_id)
    if user is None:
        raise credentials_exception
    
    return user


def get_current_active_user(
    current_user: Annotated[Usuario, Depends(get_current_user)]
) -> Usuario:
    """Obtener usuario actual activo"""
    if not current_user.activo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Usuario inactivo"
        )
    return current_user


def _check_user_roles(session: Session, user_id: int, required_roles: list[str]) -> bool:
    """
    Función auxiliar para verificar si un usuario tiene alguno de los roles requeridos
    
    Args:
        session: Sesión de base de datos
        user_id: ID del usuario
        required_roles: Lista de roles requeridos (cualquiera de ellos es válido)
    
    Returns:
        bool: True si el usuario tiene al menos uno de los roles requeridos
    """
    user_roles = UserService.get_user_roles(session, user_id)
    role_names = [role.tipo for role in user_roles]
    return any(role in role_names for role in required_roles)


def require_role(required_role: str):
    """
    Factory function para crear dependencias que requieren un rol específico
    
    Args:
        required_role: Nombre del rol requerido
    
    Returns:
        Función de dependencia que verifica el rol
    """
    def role_checker(
        current_user: Annotated[Usuario, Depends(get_current_active_user)],
        session: Session = Depends(get_session)
    ) -> Usuario:
        if not _check_user_roles(session, current_user.id, [required_role]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Se requiere rol: {required_role}"
            )
        return current_user
    return role_checker


def require_admin(
    current_user: Annotated[Usuario, Depends(get_current_active_user)],
    session: Session = Depends(get_session)
) -> Usuario:
    """
    Dependencia que requiere permisos de administrador
    
    Args:
        current_user: Usuario actual autenticado y activo
        session: Sesión de base de datos
    
    Returns:
        Usuario: El usuario actual si tiene permisos de administrador
    
    Raises:
        HTTPException: 403 si el usuario no tiene permisos de administrador
    """
    admin_roles = ["superadmin", "admin", "administrador"]
    
    if not _check_user_roles(session, current_user.id, admin_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren permisos de administrador"
        )
    
    return current_user


def require_superadmin(
    current_user: Annotated[Usuario, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> Usuario:
    if not _check_user_roles(session, current_user.id, ["superadmin"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren permisos de superadmin",
        )
    return current_user


# Funciones de conveniencia para roles comunes
def require_socio(
    current_user: Annotated[Usuario, Depends(get_current_active_user)],
    session: Session = Depends(get_session)
) -> Usuario:
    """
    Dependencia que requiere rol de socio
    
    Args:
        current_user: Usuario actual autenticado y activo
        session: Sesión de base de datos
    
    Returns:
        Usuario: El usuario actual si tiene rol de socio
    
    Raises:
        HTTPException: 403 si el usuario no tiene rol de socio
    """
    if not _check_user_roles(session, current_user.id, ["socio"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de socio"
        )
    
    return current_user


def require_admin_or_socio(
    current_user: Annotated[Usuario, Depends(get_current_active_user)],
    session: Session = Depends(get_session)
) -> Usuario:
    """
    Dependencia que requiere rol de administrador o socio
    
    Args:
        current_user: Usuario actual autenticado y activo
        session: Sesión de base de datos
    
    Returns:
        Usuario: El usuario actual si tiene rol de administrador o socio
    
    Raises:
        HTTPException: 403 si el usuario no tiene ninguno de los roles requeridos
    """
    allowed_roles = ["superadmin", "admin", "administrador", "socio"]
    
    if not _check_user_roles(session, current_user.id, allowed_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de administrador o socio"
        )
    
    return current_user


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(AUTH_RATE_LIMIT)
def register_user(request: Request, user: UserCreate, session: Session = Depends(get_session)):
    """
    Registrar un nuevo usuario
    
    Crea automáticamente:
    - Usuario con rol configurado para registro (por defecto: administrador)
    - Nivel inicial (Bronce)
    - Código QR para usar en puntos de venta
    """
    # Verificar si el email ya existe
    existing_user = UserService.get_user_by_email(session, user.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email ingresado ya está registrado"
        )

    # Verificar si el nombre de usuario ya existe
    existing_username = UserService.get_user_by_username(session, user.nombre_usuario)
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El nombre de usuario ingresado ya está registrado"
        )

    # Crear usuario con manejo de race conditions
    try:
        db_user = UserService.create_user(
            session=session,
            nombre_usuario=user.nombre_usuario,
            email=user.email,
            password=user.password,
            nombre=user.nombres,
            apellido=user.apellidos,
            sexo=user.sexo,
            fecha_nacimiento=user.fecha_nac,
            telefono=user.telefono,
            activo=False,
            role_tipo=settings.registration_default_role,
        )
    except ValueError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Configuración de roles inválida"
        )
    except IntegrityError as e:
        session.rollback()
        # El constraint único de la BD atrapó la race condition
        error_msg = str(e).lower()
        if 'email' in error_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El email ingresado ya está registrado"
            )
        elif 'nombre_usuario' in error_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El nombre de usuario ingresado ya está registrado"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El usuario no pudo ser registrado. Verifica los datos e intenta nuevamente."
            )
    
    # Mapear campos del modelo Usuario al schema UserRead
    user_read = UserRead(
        id=db_user.id,
        id_ext=str(db_user.id_ext),  # Convertir UUID a string
        nombre_usuario=db_user.nombre_usuario,
        email=db_user.email,
        nombres=db_user.nombres,  # Usar nombres directamente
        apellidos=db_user.apellidos,  # Usar apellidos directamente
        sexo=db_user.sexo.value if getattr(db_user, "sexo", None) else None,
        fecha_nac=db_user.fecha_nac,  # Usar fecha_nac directamente
        telefono=db_user.telefono,
        activo=db_user.activo,
        verificado=db_user.verificado,
        fecha_creacion=db_user.fecha_creacion,
        ultimo_login=db_user.ultimo_login,
        intentos_login_fallidos=db_user.intentos_login_fallidos
    )
    
    raw_token, expires_at = EmailVerificationService.create_token(session, db_user, expires_in_minutes=60 * 24)
    verification_link = f"{settings.frontend_url}/verify-email?token={raw_token}"
    email_sent = EmailService.send_email_verification(to_email=db_user.email, verification_link=verification_link)

    response = RegisterResponse(
        message=(
            "Te registraste correctamente. Te enviamos un email para confirmar tu cuenta. "
            "Una vez que lo confirmes, vas a poder iniciar sesión."
            if email_sent
            else "Te registraste correctamente. En este momento no pudimos enviarte el email de verificación. "
                 "Intentá reenviarlo desde el login o probá más tarde."
        ),
        user=user_read,
    )
    if settings.environment != "production":
        response.verification_link = verification_link
        response.verification_expires_at = expires_at.isoformat()
    return response


@router.post("/login", response_model=Token)
@limiter.limit(AUTH_RATE_LIMIT)
def login_user(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Session = Depends(get_session)
):
    """
    Iniciar sesión con OAuth2 (username/password form)
    
    - **username**: Email o nombre de usuario
    - **password**: Contraseña
    
    Retorna un token JWT para autenticación
    """
    # Autenticar usuario (el username puede ser email o nombre de usuario)
    user = UserService.authenticate_user(session, form_data.username, form_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email/usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.verificado:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email no verificado"
        )

    if not user.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cuenta pendiente de habilitación"
        )
    
    # Crear token de acceso
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email},
        expires_delta=access_token_expires
    )

    # Crear refresh token
    refresh_token, refresh_jti, refresh_expires_at = create_refresh_token(
        data={"sub": str(user.id), "email": user.email}
    )
    store_refresh_token(
        session,
        user_id=user.id,
        refresh_token=refresh_token,
        jti=refresh_jti,
        expires_at=refresh_expires_at,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
        refresh_token=refresh_token
    )


@router.post("/login-json", response_model=Token)
@limiter.limit(AUTH_RATE_LIMIT)
def login_user_json(
    request: Request,
    user_login: LoginJSONRequest,
    session: Session = Depends(get_session)
):
    """
    Iniciar sesión con JSON (alternativa a OAuth2 form)
    
    - **email**: Email del usuario
    - **password**: Contraseña
    
    Retorna un token JWT para autenticación
    """
    # Autenticar usuario con email
    user = UserService.authenticate_user(session, user_login.email, user_login.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
        )
    
    if not user.verificado:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email no verificado"
        )

    if not user.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cuenta pendiente de habilitación"
        )
    
    # Crear token de acceso
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email},
        expires_delta=access_token_expires
    )

    # Crear refresh token
    refresh_token, refresh_jti, refresh_expires_at = create_refresh_token(
        data={"sub": str(user.id), "email": user.email}
    )
    store_refresh_token(
        session,
        user_id=user.id,
        refresh_token=refresh_token,
        jti=refresh_jti,
        expires_at=refresh_expires_at,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
        refresh_token=refresh_token
    )


@router.get("/me", response_model=UserWithRoles)
def read_current_user(
    current_user: Annotated[Usuario, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
):
    """
    Obtener información del usuario autenticado
    
    Requiere token JWT válido en el header:
    Authorization: Bearer <token>
    """
    sexo = None
    raw_sexo = getattr(current_user, "sexo", None)
    if raw_sexo:
        sexo = raw_sexo.value if hasattr(raw_sexo, "value") else str(raw_sexo).strip() or None

    role_rows = session.exec(
        select(UsuarioRol, TipoRolUsuario)
        .join(TipoRolUsuario, TipoRolUsuario.id == UsuarioRol.id_rol)
        .where(UsuarioRol.id_usuario == current_user.id)
        .where(UsuarioRol.fecha_revocacion == None)
    ).all()
    roles = [
        RolRead(
            id=int(rol.id),
            tipo_rol_usuario=TipoRolUsuarioRead(
                id=int(rol.id),
                nombre=rol.tipo,
                descripcion=rol.descripcion,
            ),
            asignado_el=ur.fecha_asignacion,
        )
        for ur, rol in role_rows
        if rol is not None and rol.id is not None
    ]

    return UserWithRoles(
        id=current_user.id,
        id_ext=str(current_user.id_ext),  # Convert UUID to string
        nombre_usuario=current_user.nombre_usuario,
        email=current_user.email,
        nombres=current_user.nombres,  # Use correct field name 'nombres'
        apellidos=current_user.apellidos,  # Use correct field name 'apellidos'
        sexo=sexo,
        fecha_nac=current_user.fecha_nac,  # Use correct field name 'fecha_nac'
        telefono=current_user.telefono,
        activo=current_user.activo,
        verificado=current_user.verificado,
        fecha_creacion=current_user.fecha_creacion,
        ultimo_login=current_user.ultimo_login,
        intentos_login_fallidos=current_user.intentos_login_fallidos,
        roles=roles,
    )


@router.post("/refresh", response_model=Token)
@limiter.limit(PASSWORD_RATE_LIMIT)
def refresh_access_token(
    request: Request,
    body: RefreshTokenRequest,
    session: Session = Depends(get_session)
):
    """
    Renovar token de acceso usando refresh token
    """
    refresh_token = body.refresh_token
    payload = verify_token(refresh_token, expected_type="refresh")
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de refresh inválido"
        )

    refresh_jti = payload.get("jti")
    if not refresh_jti:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de refresh inválido")

    token_hash = compute_refresh_token_hash(refresh_token)
    record = get_refresh_token_by_hash(session, token_hash)
    if not record or record.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de refresh inválido")
    if record.jti != refresh_jti:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de refresh inválido")
    if record.expires_at < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de refresh expirado")
    
    user_id_str = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de refresh inválido"
        )
    
    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de refresh inválido"
        )
    
    user = session.get(Usuario, user_id)
    if user is None or not user.activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o inactivo"
        )
    
    # Crear nuevo token de acceso
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email},
        expires_delta=access_token_expires
    )

    new_refresh_token, new_refresh_jti, new_refresh_expires_at = create_refresh_token(
        data={"sub": str(user.id), "email": user.email}
    )
    revoke_refresh_token(session, record, replaced_by_refresh_token=new_refresh_token)
    store_refresh_token(
        session,
        user_id=user.id,
        refresh_token=new_refresh_token,
        jti=new_refresh_jti,
        expires_at=new_refresh_expires_at,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
        refresh_token=new_refresh_token,
    )


@router.post("/forgot-password")
@limiter.limit(PASSWORD_RATE_LIMIT)
def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    session: Session = Depends(get_session),
):
    email_normalized = body.email.lower().strip()
    user = UserService.get_user_by_email(session, email_normalized)

    if user and user.activo:
        raw_token, expires_at = PasswordResetService.create_reset_token(session, user, expires_in_minutes=30)
        reset_link = f"{settings.frontend_url}/reset-password?token={raw_token}"
        EmailService.send_password_reset_email(to_email=user.email, reset_link=reset_link)
        if settings.environment != "production":
            return {
                "message": "Si el email existe, te enviaremos un link para restablecer tu contraseña.",
                "reset_link": reset_link,
                "expires_at": expires_at,
            }

    return {"message": "Si el email existe, te enviaremos un link para restablecer tu contraseña."}


@router.post("/reset-password")
@limiter.limit(PASSWORD_RATE_LIMIT)
def reset_password(
    request: Request,
    body: ResetPasswordRequest,
    session: Session = Depends(get_session),
):
    try:
        PasswordResetService.reset_password(session, body.token, body.new_password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token inválido o expirado")
    return {"message": "Contraseña actualizada correctamente"}


@router.post("/verify-email")
@limiter.limit(READ_RATE_LIMIT)
def verify_email(
    request: Request,
    body: VerifyEmailRequest,
    session: Session = Depends(get_session),
):
    try:
        EmailVerificationService.verify_email(session, body.token)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token inválido o expirado")
    return {"message": "Email verificado correctamente. Ya podés iniciar sesión."}


@router.post("/resend-verification")
@limiter.limit(PASSWORD_RATE_LIMIT)
def resend_verification_email(
    request: Request,
    body: ResendVerificationRequest,
    session: Session = Depends(get_session),
):
    email_normalized = body.email.lower().strip()
    user = UserService.get_user_by_email(session, email_normalized)
    if user and not user.verificado:
        raw_token, _expires_at = EmailVerificationService.create_token(session, user, expires_in_minutes=60 * 24)
        verification_link = f"{settings.frontend_url}/verify-email?token={raw_token}"
        EmailService.send_email_verification(to_email=user.email, verification_link=verification_link)
    return {"message": "Si el email existe, te enviaremos un link para confirmar tu cuenta."}


# Exportar funciones de dependencia para usar en otros routers
__all__ = [
    "get_current_user",
    "get_current_active_user",
    "require_admin",
    "require_superadmin",
    "require_role",
    "require_socio",
    "require_admin_or_socio"
]
