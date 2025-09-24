from typing import List
from fastapi import HTTPException, status, Depends
from app.models.user import User, UserRole
from app.routers.auth import get_current_active_user


def require_roles(allowed_roles: List[UserRole]):
    """Decorador para requerir roles específicos"""
    def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos suficientes para realizar esta acción"
            )
        return current_user
    return role_checker


def require_admin(current_user: User = Depends(get_current_active_user)) -> User:
    """Requerir rol de administrador"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren permisos de administrador"
        )
    return current_user


def require_user_or_admin(current_user: User = Depends(get_current_active_user)) -> User:
    """Requerir rol de usuario o administrador"""
    if current_user.role not in [UserRole.USER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren permisos de usuario o administrador"
        )
    return current_user


def check_user_ownership_or_admin(user_id: int, current_user: User) -> bool:
    """Verificar si el usuario actual es el propietario del recurso o es admin"""
    return current_user.id == user_id or current_user.role == UserRole.ADMIN