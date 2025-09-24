from typing import List, Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.core.database import get_session
from app.core.auth import require_admin, require_user_or_admin, check_user_ownership_or_admin
from app.core.security import get_password_hash
from app.models.user import User, UserCreate, UserRead, UserUpdate
from app.routers.auth import get_current_active_user
from datetime import datetime

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    user: UserCreate, 
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin)
):
    """Crear un nuevo usuario (solo administradores)"""
    # Verificar si el email ya existe
    existing_user = session.exec(select(User).where(User.email == user.email)).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email ya está registrado"
        )
    
    # Crear nuevo usuario con contraseña hasheada
    user_data = user.model_dump(exclude={"password"})
    password_hash = get_password_hash(user.password)
    
    db_user = User(**user_data, password_hash=password_hash)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


@router.get("/", response_model=List[UserRead])
def read_users(
    skip: int = 0, 
    limit: int = 100, 
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin)
):
    """Obtener lista de usuarios (solo administradores)"""
    users = session.exec(select(User).offset(skip).limit(limit)).all()
    return users


@router.get("/{user_id}", response_model=UserRead)
def read_user(
    user_id: int, 
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
):
    """Obtener un usuario por ID (propio perfil o administradores)"""
    # Verificar permisos: propio perfil o administrador
    if not check_user_ownership_or_admin(user_id, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para ver este usuario"
        )
    
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    return user


@router.put("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int, 
    user_update: UserUpdate, 
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
):
    """Actualizar un usuario (propio perfil o administradores)"""
    # Verificar permisos: propio perfil o administrador
    if not check_user_ownership_or_admin(user_id, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para actualizar este usuario"
        )
    
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    
    # Actualizar campos proporcionados
    user_data = user_update.model_dump(exclude_unset=True)
    
    # Solo administradores pueden cambiar roles
    if "role" in user_data and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo administradores pueden cambiar roles"
        )
    
    for field, value in user_data.items():
        setattr(user, field, value)
    
    user.updated_at = datetime.utcnow()
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int, 
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin)
):
    """Eliminar un usuario (solo administradores)"""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    
    # Evitar que un admin se elimine a sí mismo
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes eliminar tu propio usuario"
        )
    
    session.delete(user)
    session.commit()
    return None