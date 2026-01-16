"""
Modelos de puntos de venta, equipos y barriles para la API BeCard
"""
from sqlmodel import SQLModel, Field, Relationship, Column
from sqlalchemy import Numeric
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime, date
from decimal import Decimal
from .base import BaseModel, TimestampMixin

# Importaciones para evitar referencias circulares
if TYPE_CHECKING:
    from .user_extended import Usuario
    from .beer import Cerveza
    from .sales import Venta
    from .tenant import Tenant



class TipoEstadoEquipo(BaseModel, table=True):
    """Estados de equipos (inactiva, activo, en mantenimiento)"""
    __tablename__ = "tipos_estado_equipo"
    
    estado: str = Field(max_length=50, unique=True)
    permite_ventas: bool = Field(default=True, description="Si el estado permite realizar ventas")
    
    # Relaciones
    equipos: List["Equipo"] = Relationship(back_populates="estado_equipo")


class TipoBarril(BaseModel, table=True):
    """Tipos de barril por capacidad"""
    __tablename__ = "tipos_barril"
    
    capacidad: int = Field(gt=0, le=1000, description="Capacidad del barril en litros")
    nombre: Optional[str] = Field(default=None, max_length=50, description="Nombre descriptivo del tipo")
    
    # Relaciones
    equipos: List["Equipo"] = Relationship(back_populates="barril_tipo")


class PuntoVenta(BaseModel, TimestampMixin, table=True):
    """Puntos de venta (solo para socios)"""
    __tablename__ = "puntos_de_venta"
    
    nombre: str = Field(max_length=50)
    calle: str = Field(max_length=50)
    altura: int = Field(gt=0)
    localidad: str = Field(max_length=50)
    provincia: str = Field(max_length=50)
    codigo_postal: Optional[str] = Field(default=None, max_length=10)
    telefono: Optional[str] = Field(default=None, max_length=20)
    email: Optional[str] = Field(default=None, max_length=100)
    horario_apertura: Optional[str] = Field(default=None, description="Horario de apertura (TIME)")
    horario_cierre: Optional[str] = Field(default=None, description="Horario de cierre (TIME)")
    id_usuario_socio: Optional[int] = Field(foreign_key="usuarios.id", default=None)
    tenant_id: Optional[int] = Field(foreign_key="tenants.id", default=None, index=True)
    activo: bool = Field(default=True, description="Si el punto de venta está activo")
    
    # Relaciones
    socio: Optional["Usuario"] = Relationship(
        back_populates="puntos_venta",
        sa_relationship_kwargs={"foreign_keys": "PuntoVenta.id_usuario_socio"}
    )
    tenant: Optional["Tenant"] = Relationship()
    equipos: List["Equipo"] = Relationship(back_populates="punto_venta")
    # reglas_precio: List["ReglaDePrecioEntidad"] = Relationship(back_populates="punto_venta")  # DEPRECATED


class Equipo(BaseModel, table=True):
    """Equipos de dispensado de cerveza"""
    __tablename__ = "equipos"
    
    id_estado_equipo: int = Field(foreign_key="tipos_estado_equipo.id")
    id_barril: int = Field(foreign_key="tipos_barril.id")
    nombre_equipo: Optional[str] = Field(max_length=50, default=None)
    capacidad_actual: int = Field(ge=0, description="Capacidad actual en litros")
    temperatura_actual: Optional[Decimal] = Field(
        default=None,
        sa_column=Column(Numeric(4, 2)),
        description="Temperatura actual del equipo"
    )
    ultima_limpieza: Optional[date] = Field(default=None, description="Fecha de última limpieza")
    proxima_limpieza: Optional[date] = Field(default=None, description="Fecha de próxima limpieza")
    creado_el: datetime = Field(default_factory=datetime.utcnow)
    id_punto_de_venta: Optional[int] = Field(foreign_key="puntos_de_venta.id", default=None)
    id_cerveza: Optional[int] = Field(foreign_key="cervezas.id", default=None)
    activo: bool = Field(default=True, description="Si el equipo está activo")
    
    # Relaciones
    estado_equipo: TipoEstadoEquipo = Relationship(back_populates="equipos")
    barril_tipo: TipoBarril = Relationship(back_populates="equipos")
    punto_venta: Optional[PuntoVenta] = Relationship(back_populates="equipos")
    cerveza: Optional["Cerveza"] = Relationship(back_populates="equipos")
    ventas: List["Venta"] = Relationship(back_populates="equipo")
    # reglas_precio: List["ReglaDePrecioEntidad"] = Relationship(back_populates="equipo")  # DEPRECATED


# DEPRECATED: EquipoBarril eliminado - relación directa via id_barril en Equipo


# Esquemas Pydantic para API

class TipoEstadoEquipoBase(SQLModel):
    """Esquema base para tipo de estado de equipo"""
    estado: str = Field(max_length=50)
    permite_ventas: bool = Field(default=True)


class TipoEstadoEquipoCreate(TipoEstadoEquipoBase):
    """Esquema para crear tipo de estado de equipo"""
    pass


class TipoEstadoEquipoRead(TipoEstadoEquipoBase):
    """Esquema para leer tipo de estado de equipo"""
    id: int
    id_ext: str


class TipoBarrilBase(SQLModel):
    """Esquema base para tipo de barril"""
    capacidad: int = Field(gt=0, le=1000)
    nombre: Optional[str] = Field(default=None, max_length=50)


class TipoBarrilCreate(TipoBarrilBase):
    """Esquema para crear tipo de barril"""
    pass


class TipoBarrilRead(TipoBarrilBase):
    """Esquema para leer tipo de barril"""
    id: int
    id_ext: str


class PuntoVentaBase(SQLModel):
    """Esquema base para punto de venta"""
    nombre: str = Field(max_length=50)
    calle: str = Field(max_length=50)
    altura: int = Field(gt=0)
    localidad: str = Field(max_length=50)
    provincia: str = Field(max_length=50)
    codigo_postal: Optional[str] = Field(default=None, max_length=10)
    telefono: Optional[str] = Field(default=None, max_length=20)
    email: Optional[str] = Field(default=None, max_length=100)
    horario_apertura: Optional[str] = None
    horario_cierre: Optional[str] = None
    activo: bool = Field(default=True)


class PuntoVentaCreate(PuntoVentaBase):
    """Esquema para crear punto de venta"""
    id_usuario_socio: Optional[int] = None


class PuntoVentaRead(PuntoVentaBase):
    """Esquema para leer punto de venta"""
    id: int
    id_ext: str
    creado_el: datetime
    creado_por: Optional[int]
    id_usuario_socio: Optional[int]


class PuntoVentaUpdate(SQLModel):
    """Esquema para actualizar punto de venta"""
    nombre: Optional[str] = Field(default=None, max_length=50)
    calle: Optional[str] = Field(default=None, max_length=50)
    altura: Optional[int] = Field(default=None, gt=0)
    localidad: Optional[str] = Field(default=None, max_length=50)
    provincia: Optional[str] = Field(default=None, max_length=50)
    codigo_postal: Optional[str] = Field(default=None, max_length=10)
    telefono: Optional[str] = Field(default=None, max_length=20)
    email: Optional[str] = Field(default=None, max_length=100)
    horario_apertura: Optional[str] = None
    horario_cierre: Optional[str] = None
    activo: Optional[bool] = None
    id_usuario_socio: Optional[int] = None


class EquipoBase(SQLModel):
    """Esquema base para equipo"""
    nombre_equipo: Optional[str] = Field(default=None, max_length=50)
    id_barril: int
    capacidad_actual: int = Field(ge=0)
    temperatura_actual: Optional[Decimal] = None
    ultima_limpieza: Optional[date] = None
    proxima_limpieza: Optional[date] = None
    id_estado_equipo: int
    id_punto_de_venta: Optional[int] = None
    id_cerveza: Optional[int] = None


class EquipoCreate(EquipoBase):
    """Esquema para crear equipo"""
    pass


class EquipoRead(EquipoBase):
    """Esquema para leer equipo"""
    id: int
    id_ext: str
    creado_el: datetime


class EquipoUpdate(SQLModel):
    """Esquema para actualizar equipo"""
    nombre_equipo: Optional[str] = Field(default=None, max_length=50)
    id_barril: Optional[int] = None
    capacidad_actual: Optional[int] = Field(default=None, ge=0)
    temperatura_actual: Optional[Decimal] = None
    ultima_limpieza: Optional[date] = None
    proxima_limpieza: Optional[date] = None
    id_estado_equipo: Optional[int] = None
    id_punto_de_venta: Optional[int] = None
    id_cerveza: Optional[int] = None
