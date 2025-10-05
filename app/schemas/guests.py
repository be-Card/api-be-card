"""
Esquemas Pydantic para clientes guest
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date


class GuestCustomerCreate(BaseModel):
    """Esquema para registrar cliente guest en punto de venta"""
    nombres: str = Field(max_length=100)
    apellidos: str = Field(max_length=100)
    telefono: Optional[str] = Field(default=None, max_length=20)
    sexo: Optional[str] = Field(default=None, description="MASCULINO/FEMENINO")
    fecha_nac: Optional[date] = Field(default=None)


class GuestCustomerRead(BaseModel):
    """Respuesta al registrar guest"""
    id: int
    codigo_cliente: str
    nombres: str
    apellidos: str
    telefono: Optional[str]
    fecha_creacion: datetime
    tipo_registro: str
    mensaje: str = "Cliente guest registrado. Guarde el código para futuras compras."


class GuestLookup(BaseModel):
    """Buscar cliente guest por código"""
    codigo_cliente: str = Field(description="Código QR del cliente")


class GuestUpgradeRequest(BaseModel):
    """Esquema para que guest se registre en app"""
    codigo_cliente: str = Field(description="Código QR actual del cliente")
    nombre_usuario: str = Field(max_length=50, description="Nombre de usuario deseado")
    email: str = Field(description="Email para la cuenta")
    password: str = Field(min_length=8, description="Contraseña (mínimo 8 caracteres)")
    sexo: Optional[str] = Field(default=None, description="MASCULINO/FEMENINO (si no lo tenía)")
    fecha_nac: Optional[date] = Field(default=None, description="Fecha de nacimiento (si no la tenía)")


class GuestStats(BaseModel):
    """Estadísticas del cliente guest"""
    codigo_cliente: str
    nombres: str
    apellidos: str
    puntos_totales: int
    nivel_actual: str
    total_compras: int
    monto_total_gastado: float
    fecha_registro: datetime
    puede_actualizar_cuenta: bool
