"""
Modelos base y enums para la API BeCard
"""
from enum import Enum
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
import uuid


class TipoPrioridadRegla(str, Enum):
    """Enum para prioridad de reglas de precio"""
    BAJA = "baja"
    MEDIA = "media"
    ALTA = "alta"


class TipoSexo(str, Enum):
    """Enum para tipo de sexo"""
    FEMENINO = "F"
    MASCULINO = "M"


class TipoEstadoPago(str, Enum):
    """Enum para estado de pago"""
    APROBADO = "aprobado"
    RECHAZADO = "rechazado"
    PENDIENTE = "pendiente"


class TipoAlcanceRegla(str, Enum):
    """Enum para alcance de regla de precio"""
    CERVEZA = "cerveza"
    PUNTO_DE_VENTA = "punto_de_venta"
    EQUIPO = "equipo"


class BaseModel(SQLModel):
    """Modelo base con campos comunes para todas las entidades"""
    id: Optional[int] = Field(default=None, primary_key=True)
    id_ext: uuid.UUID = Field(default_factory=uuid.uuid4, unique=True, index=True)


class TimestampMixin(SQLModel):
    """Mixin para campos de timestamp comunes"""
    creado_el: datetime = Field(default_factory=datetime.utcnow, index=True)
    creado_por: Optional[int] = Field(default=None, foreign_key="usuarios.id")


class BaseModelWithTimestamp(BaseModel, TimestampMixin):
    """Modelo base que combina BaseModel con TimestampMixin"""
    pass