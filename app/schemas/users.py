"""
Esquemas Pydantic para usuarios (API)
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime


# Esquemas para TipoRolUsuario
class TipoRolUsuarioRead(BaseModel):
    id: int
    nombre: str = Field(max_length=50)  # Frontend expects 'nombre' field
    descripcion: Optional[str] = None

class RolRead(BaseModel):
    id: int
    tipo_rol_usuario: TipoRolUsuarioRead
    asignado_el: datetime  # Frontend expects 'asignado_el' field


# Esquemas para TipoNivelUsuario
class NivelBase(BaseModel):
    nivel: str = Field(max_length=50)
    puntaje_minimo: int = Field(ge=0)  # Frontend expects 'puntaje_minimo'
    puntaje_max: Optional[int] = None
    beneficios: Optional[str] = None


class NivelRead(NivelBase):
    id: int


# Esquemas para Usuario
class UserBase(BaseModel):
    nombre_usuario: str = Field(max_length=50)
    email: EmailStr
    nombres: str = Field(max_length=50)  # Changed from 'nombre' to 'nombres' to match database
    apellidos: str = Field(max_length=50)  # Changed from 'apellido' to 'apellidos' to match database
    sexo: str
    fecha_nac: datetime  # Changed from 'fecha_nacimiento' to 'fecha_nac' to match database
    telefono: Optional[str] = Field(default=None, max_length=20)


class UserCreate(UserBase):
    """Esquema para crear usuario"""
    password: str = Field(min_length=8, description="Contraseña (mínimo 8 caracteres)")


class UserUpdate(BaseModel):
    """Esquema para actualizar usuario"""
    nombres: Optional[str] = Field(default=None, max_length=50)  # Changed from 'nombre' to 'nombres'
    apellidos: Optional[str] = Field(default=None, max_length=50)  # Changed from 'apellido' to 'apellidos'
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
