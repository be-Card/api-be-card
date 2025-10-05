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
from app.schemas.auth import Token, TokenData, LoginJSONRequest
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
    if user_id is None:
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


def require_role(required_role: str):
    """Decorator para requerir un rol específico"""
    def role_checker(current_user: Annotated[Usuario, Depends(get_current_active_user)]):
        user_roles = UserService.get_user_roles(session, current_user.id)
        role_names = [role.rol for role in user_roles]
        
        if required_role not in role_names:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Se requiere rol: {required_role}"
            )
        return current_user
    return role_checker


def require_admin(current_user: Annotated[Usuario, Depends(get_current_active_user)]) -> Usuario:
    """Requerir rol de administrador"""
    # Obtener session desde el contexto (necesitamos refactorizar esto)
    # Por ahora, verificamos directamente
    # TODO: Mejorar esto cuando tengamos dependencia de session inyectada
    if not hasattr(current_user, '_roles_checked'):
        from app.core.database import engine
        with Session(engine) as session:
            user_roles = UserService.get_user_roles(session, current_user.id)
            role_names = [role.rol for role in user_roles]
            if "administrador" not in role_names and "admin" not in role_names:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Se requieren permisos de administrador"
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
            detail="El email ya está registrado"
        )
    
    # Verificar si el nombre de usuario ya existe
    existing_username = UserService.get_user_by_username(session, user.nombre_usuario)
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El nombre de usuario ya está registrado"
        )
    
    # Crear nuevo usuario
    db_user = UserService.create_user(
        session,
        nombre_usuario=user.nombre_usuario,
        email=user.email,
        password=user.password,
        nombre=user.nombre,
        apellido=user.apellido,
        sexo=user.sexo,
        fecha_nacimiento=user.fecha_nacimiento,
        telefono=user.telefono
    )
    
    return db_user


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
    return current_user


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
    "require_role"
]