"""
Router de autenticación - Refactorizado para usar Usuario
"""
from datetime import datetime, timedelta
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlmodel import Session

from app.core.database import get_session
from app.core.security import create_access_token, verify_token
from app.core.config import settings
from app.services.users import UserService
from app.models.user_extended import Usuario
from app.schemas.auth import Token, LoginJSONRequest
from app.schemas.users import UserCreate, UserRead

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
    
    payload = verify_token(token)
    if payload is None:
        raise credentials_exception
    
    user_id: int = payload.get("sub")
    
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
    admin_roles = ["administrador", "admin"]
    
    if not _check_user_roles(session, current_user.id, admin_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren permisos de administrador"
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
    allowed_roles = ["administrador", "admin", "socio"]
    
    if not _check_user_roles(session, current_user.id, allowed_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de administrador o socio"
        )
    
    return current_user


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_user(user: UserCreate, session: Session = Depends(get_session)):
    """
    Registrar un nuevo usuario (cliente)
    
    Crea automáticamente:
    - Usuario con rol 'usuario' (cliente)
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
    
    # Crear usuario
    db_user = UserService.create_user(
        session=session,
        nombre_usuario=user.nombre_usuario,
        email=user.email,
        password=user.password,
        nombre=user.nombres,
        apellido=user.apellidos,
        sexo=user.sexo,
        fecha_nacimiento=user.fecha_nac,
        telefono=user.telefono
    )
    
    # Mapear campos del modelo Usuario al schema UserRead
    user_read = UserRead(
        id=db_user.id,
        id_ext=str(db_user.id_ext),  # Convertir UUID a string
        nombre_usuario=db_user.nombre_usuario,
        email=db_user.email,
        nombres=db_user.nombres,  # Usar nombres directamente
        apellidos=db_user.apellidos,  # Usar apellidos directamente
        sexo=db_user.sexo.value if db_user.sexo else "",  # Convertir enum a string
        fecha_nac=db_user.fecha_nac,  # Usar fecha_nac directamente
        telefono=db_user.telefono,
        activo=db_user.activo,
        verificado=db_user.verificado,
        fecha_creacion=db_user.fecha_creacion,
        ultimo_login=db_user.ultimo_login,
        intentos_login_fallidos=db_user.intentos_login_fallidos
    )
    
    return user_read


@router.post("/login", response_model=Token)
def login_user(
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
    
    if not user.activo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario inactivo"
        )
    
    # Crear token de acceso
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email},
        expires_delta=access_token_expires
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60
    )


@router.post("/login-json", response_model=Token)
def login_user_json(
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
    
    if not user.activo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario inactivo"
        )
    
    # Crear token de acceso
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email},
        expires_delta=access_token_expires
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60
    )


@router.get("/me", response_model=UserRead)
def read_current_user(
    current_user: Annotated[Usuario, Depends(get_current_active_user)]
):
    """
    Obtener información del usuario autenticado
    
    Requiere token JWT válido en el header:
    Authorization: Bearer <token>
    """
    # Convert Usuario model to UserRead schema with proper field mapping
    return UserRead(
        id=current_user.id,
        id_ext=str(current_user.id_ext),  # Convert UUID to string
        nombre_usuario=current_user.nombre_usuario,
        email=current_user.email,
        nombres=current_user.nombres,  # Use correct field name 'nombres'
        apellidos=current_user.apellidos,  # Use correct field name 'apellidos'
        sexo=current_user.sexo.value if current_user.sexo else "",  # Convert enum to string
        fecha_nac=datetime.combine(current_user.fecha_nac, datetime.min.time()) if current_user.fecha_nac else datetime.now(),  # Use correct field name 'fecha_nac'
        telefono=current_user.telefono,
        activo=current_user.activo,
        verificado=current_user.verificado,
        fecha_creacion=current_user.fecha_creacion,
        ultimo_login=current_user.ultimo_login,
        intentos_login_fallidos=current_user.intentos_login_fallidos
    )


@router.post("/refresh", response_model=Token)
def refresh_access_token(
    refresh_token: str,
    session: Session = Depends(get_session)
):
    """
    Renovar token de acceso usando refresh token
    
    **Nota:** Implementación básica. En producción considerar:
    - Almacenar refresh tokens en BD
    - Rotación de refresh tokens
    - Blacklist de tokens revocados
    """
    payload = verify_token(refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de refresh inválido"
        )
    
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de refresh inválido"
        )
    
    user = session.get(Usuario, int(user_id))
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
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60
    )


# Exportar funciones de dependencia para usar en otros routers
__all__ = [
    "get_current_user",
    "get_current_active_user",
    "require_admin",
    "require_role",
    "require_socio",
    "require_admin_or_socio"
]