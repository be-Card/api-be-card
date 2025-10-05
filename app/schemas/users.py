"""
Esquemas Pydantic para usuarios (API)
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime


# Esquemas para TipoRolUsuario
class RolBase(BaseModel):
    rol: str = Field(max_length=50)
    descripcion: Optional[str] = None


class RolRead(RolBase):
    id: int
    creado_el: datetime


# Esquemas para TipoNivelUsuario
class NivelBase(BaseModel):
    nivel: str = Field(max_length=50)
    puntaje_minimo: int = Field(ge=0)
    puntaje_max: Optional[int] = None
    beneficios: Optional[str] = None


class NivelRead(NivelBase):
    id: int


# Esquemas para Usuario
class UserBase(BaseModel):
    nombre_usuario: str = Field(max_length=50)
    email: EmailStr
    nombre: str = Field(max_length=50)
    apellido: str = Field(max_length=50)
    sexo: str
    fecha_nacimiento: datetime
    telefono: Optional[str] = Field(default=None, max_length=20)


class UserCreate(UserBase):
    """Esquema para crear usuario"""
    password: str = Field(min_length=8, description="Contraseña (mínimo 8 caracteres)")


class UserUpdate(BaseModel):
    """Esquema para actualizar usuario"""
    nombre: Optional[str] = Field(default=None, max_length=50)
    apellido: Optional[str] = Field(default=None, max_length=50)
    telefono: Optional[str] = Field(default=None, max_length=20)
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(default=None, min_length=8)


class UserRead(UserBase):
    """Esquema para leer usuario (respuesta)"""
    id: int
    id_ext: str
    activo: bool
    verificado: bool
    fecha_creacion: datetime
    ultimo_login: Optional[datetime] = None
    intentos_login_fallidos: int


class UserWithRoles(UserRead):
    """Esquema para usuario con roles y nivel"""
    roles: List[RolRead] = []
    nivel: Optional[NivelRead] = None


# UserLogin movido a schemas/auth.py


class PasswordChange(BaseModel):
    """Esquema para cambio de contraseña"""
    old_password: str
    new_password: str = Field(min_length=8)


class RoleAssignment(BaseModel):
    """Esquema para asignar rol"""
    role_id: int


# Respuestas genéricas
class MessageResponse(BaseModel):
    """Respuesta genérica con mensaje"""
    message: str


class UserListResponse(BaseModel):
    """Respuesta para lista de usuarios"""
    users: List[UserRead]
    total: int
    skip: int
    limit: int
