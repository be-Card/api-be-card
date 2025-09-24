from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    """Roles de usuario"""
    ADMIN = "admin"
    USER = "user"


class UserBase(SQLModel):
    """Modelo base para Usuario"""
    name: str = Field(max_length=100)
    email: str = Field(unique=True, index=True, max_length=255)
    is_active: bool = Field(default=True)
    role: UserRole = Field(default=UserRole.USER)


class User(UserBase, table=True):
    """Modelo de Usuario para la base de datos"""
    id: Optional[int] = Field(default=None, primary_key=True)
    password_hash: str = Field(max_length=255)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)
    last_login: Optional[datetime] = Field(default=None)


class UserCreate(UserBase):
    """Esquema para crear un usuario"""
    password: str = Field(min_length=8, max_length=100)


class UserRead(UserBase):
    """Esquema para leer un usuario"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None


class UserUpdate(SQLModel):
    """Esquema para actualizar un usuario"""
    name: Optional[str] = Field(default=None, max_length=100)
    email: Optional[str] = Field(default=None, max_length=255)
    is_active: Optional[bool] = Field(default=None)
    role: Optional[UserRole] = Field(default=None)


class UserLogin(SQLModel):
    """Esquema para login de usuario"""
    email: str = Field(max_length=255)
    password: str = Field(min_length=1, max_length=100)


class Token(SQLModel):
    """Esquema para token de acceso"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(SQLModel):
    """Datos del token"""
    user_id: Optional[int] = None
    email: Optional[str] = None