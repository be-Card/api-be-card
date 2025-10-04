"""
Modelos de cervezas, estilos y precios para la API BeCard
"""
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from decimal import Decimal
from .base import BaseModel, TimestampMixin

# Importaciones para evitar referencias circulares
if TYPE_CHECKING:
    from .user_extended import Usuario
    from .sales import Venta
    from .sales_point import Equipo
    from .pricing import ReglaDePrecioEntidad


class TipoEstiloCerveza(BaseModel, table=True):
    """Tipos de estilo de cerveza (IPA, Lager, Stout, etc.)"""
    __tablename__ = "tipos_estilo_cerveza"
    
    estilo: Optional[str] = Field(max_length=50, default=None, unique=True)
    descripcion: Optional[str] = Field(default=None, description="Descripción del estilo")
    origen: Optional[str] = Field(default=None, max_length=50, description="País/región de origen")
    
    # Relaciones
    cervezas_estilos: List["CervezaEstilo"] = Relationship(back_populates="estilo")


class Cerveza(BaseModel, TimestampMixin, table=True):
    """Modelo principal de cerveza"""
    __tablename__ = "cervezas"
    
    nombre: str = Field(max_length=50, unique=True, index=True)
    tipo: str = Field(max_length=50)
    abv: Optional[Decimal] = Field(
        default=None,
        max_digits=4,
        decimal_places=2,
        ge=0,
        le=100,
        description="Alcohol by volume (0-100%)"
    )
    ibu: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="International Bitterness Units (0-100)"
    )
    descripcion: Optional[str] = Field(default=None)
    imagen: Optional[str] = Field(default=None, description="URL o path de la imagen")
    proveedor: str = Field(max_length=50)
    activo: bool = Field(default=True, description="Si el producto está disponible")
    destacado: bool = Field(default=False, description="Si es un producto destacado")
    
    # Relaciones
    creador: "Usuario" = Relationship(back_populates="cervezas_creadas")
    estilos: List["CervezaEstilo"] = Relationship(back_populates="cerveza")
    precios_historicos: List["PrecioCerveza"] = Relationship(back_populates="cerveza")
    ventas: List["Venta"] = Relationship(back_populates="cerveza")
    equipos: List["Equipo"] = Relationship(back_populates="cerveza")
    reglas_precio: List["ReglaDePrecioEntidad"] = Relationship(back_populates="cerveza")


class CervezaEstilo(SQLModel, table=True):
    """Relación muchos a muchos entre cervezas y estilos"""
    __tablename__ = "cervezas_estilos"
    
    id_cerveza: int = Field(foreign_key="cervezas.id", primary_key=True)
    id_estilo: int = Field(foreign_key="tipos_estilo_cerveza.id", primary_key=True)
    
    # Relaciones
    cerveza: Cerveza = Relationship(back_populates="estilos")
    estilo: TipoEstiloCerveza = Relationship(back_populates="cervezas_estilos")


class PrecioCerveza(SQLModel, table=True):
    """Historial de precios de cervezas"""
    __tablename__ = "precios_cervezas"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    id_cerveza: int = Field(foreign_key="cervezas.id", index=True)
    precio: Decimal = Field(max_digits=10, decimal_places=2, gt=0)
    fecha_inicio: datetime = Field(default_factory=datetime.utcnow, index=True)
    fecha_fin: Optional[datetime] = Field(
        default=None,
        description="NULL significa que es el precio actual"
    )
    creado_por: int = Field(foreign_key="usuarios.id")
    motivo: Optional[str] = Field(default=None, description="Razón del cambio de precio")
    
    # Relaciones
    cerveza: Cerveza = Relationship(back_populates="precios_historicos")


# Esquemas Pydantic para API

class TipoEstiloCervezaBase(SQLModel):
    """Esquema base para tipo de estilo de cerveza"""
    estilo: Optional[str] = Field(max_length=50, default=None)
    descripcion: Optional[str] = None
    origen: Optional[str] = Field(default=None, max_length=50)


class TipoEstiloCervezaCreate(TipoEstiloCervezaBase):
    """Esquema para crear tipo de estilo de cerveza"""
    pass


class TipoEstiloCervezaRead(TipoEstiloCervezaBase):
    """Esquema para leer tipo de estilo de cerveza"""
    id: int
    id_ext: str


class CervezaBase(SQLModel):
    """Esquema base para cerveza"""
    nombre: str = Field(max_length=50)
    tipo: str = Field(max_length=50)
    abv: Optional[Decimal] = Field(default=None, max_digits=4, decimal_places=2, ge=0, le=100)
    ibu: Optional[int] = Field(default=None, ge=0, le=100)
    descripcion: Optional[str] = None
    imagen: Optional[str] = None
    proveedor: str = Field(max_length=50)
    activo: bool = Field(default=True)
    destacado: bool = Field(default=False)


class CervezaCreate(CervezaBase):
    """Esquema para crear cerveza"""
    estilos_ids: List[int] = Field(default=[], description="IDs de los estilos asociados")


class CervezaRead(CervezaBase):
    """Esquema para leer cerveza"""
    id: int
    id_ext: str
    creado_el: datetime
    creado_por: int
    estilos: List[TipoEstiloCervezaRead] = []


class CervezaUpdate(SQLModel):
    """Esquema para actualizar cerveza"""
    nombre: Optional[str] = Field(default=None, max_length=50)
    tipo: Optional[str] = Field(default=None, max_length=50)
    abv: Optional[Decimal] = Field(default=None, max_digits=4, decimal_places=2, ge=0, le=100)
    ibu: Optional[int] = Field(default=None, ge=0, le=100)
    descripcion: Optional[str] = None
    imagen: Optional[str] = None
    proveedor: Optional[str] = Field(default=None, max_length=50)
    activo: Optional[bool] = None
    destacado: Optional[bool] = None
    estilos_ids: Optional[List[int]] = None


class PrecioCervezaCreate(SQLModel):
    """Esquema para crear precio de cerveza"""
    id_cerveza: int
    precio: Decimal = Field(max_digits=10, decimal_places=2, gt=0)
    motivo: Optional[str] = None


class PrecioCervezaRead(SQLModel):
    """Esquema para leer precio de cerveza"""
    id: int
    id_cerveza: int
    precio: Decimal
    fecha_inicio: datetime
    fecha_fin: Optional[datetime]
    creado_por: int
    motivo: Optional[str] = None