"""
Modelos de sistema de recompensas (premios y canjes) para la API BeCard
"""
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime, date

# Importaciones para evitar referencias circulares
if TYPE_CHECKING:
    from .user_extended import Usuario


class CatalogoPremio(SQLModel, table=True):
    """
    Catálogo de premios canjeables por puntos
    """
    __tablename__ = "catalogo_premios"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(max_length=100, description="Nombre del premio")
    descripcion: Optional[str] = Field(default=None, description="Descripción del premio")
    puntos_requeridos: int = Field(gt=0, description="Puntos necesarios para canjear")
    activo: bool = Field(default=True, index=True, description="Si el premio está disponible")
    stock_disponible: Optional[int] = Field(default=None, ge=0, description="Stock disponible del premio")
    imagen: Optional[str] = Field(default=None, description="URL de la imagen del premio")
    categoria: Optional[str] = Field(default=None, max_length=50, description="Categoría del premio")
    fecha_creacion: datetime = Field(default_factory=datetime.utcnow)
    fecha_vencimiento: Optional[date] = Field(default=None, description="Fecha de vencimiento del premio")
    
    # Relaciones
    canjes: List["Canje"] = Relationship(back_populates="premio")


class Canje(SQLModel, table=True):
    """
    Registro de canjes realizados por usuarios
    """
    __tablename__ = "canjes"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    id_usuario: int = Field(foreign_key="usuarios.id", index=True)
    id_premio: int = Field(foreign_key="catalogo_premios.id", index=True)
    puntos_utilizados: int = Field(gt=0, description="Puntos utilizados en el canje")
    fecha_canje: datetime = Field(default_factory=datetime.utcnow, index=True)
    estado: str = Field(default="pendiente", max_length=20, description="pendiente, procesado, entregado, cancelado")
    notas: Optional[str] = Field(default=None, description="Notas adicionales del canje")
    
    # Relaciones
    usuario: "Usuario" = Relationship(back_populates="canjes")
    premio: CatalogoPremio = Relationship(back_populates="canjes")


# Esquemas Pydantic para API

class CatalogoPremioBase(SQLModel):
    """Esquema base para premio"""
    nombre: str = Field(max_length=100)
    descripcion: Optional[str] = None
    puntos_requeridos: int = Field(gt=0)
    activo: bool = Field(default=True)
    stock_disponible: Optional[int] = Field(default=None, ge=0)
    imagen: Optional[str] = None
    categoria: Optional[str] = Field(default=None, max_length=50)
    fecha_vencimiento: Optional[date] = None


class CatalogoPremioCreate(CatalogoPremioBase):
    """Esquema para crear premio"""
    pass


class CatalogoPremioRead(CatalogoPremioBase):
    """Esquema para leer premio"""
    id: int
    fecha_creacion: datetime


class CatalogoPremioUpdate(SQLModel):
    """Esquema para actualizar premio"""
    nombre: Optional[str] = Field(default=None, max_length=100)
    descripcion: Optional[str] = None
    puntos_requeridos: Optional[int] = Field(default=None, gt=0)
    activo: Optional[bool] = None
    stock_disponible: Optional[int] = Field(default=None, ge=0)
    imagen: Optional[str] = None
    categoria: Optional[str] = Field(default=None, max_length=50)
    fecha_vencimiento: Optional[date] = None


class CanjeBase(SQLModel):
    """Esquema base para canje"""
    id_usuario: int
    id_premio: int
    puntos_utilizados: int = Field(gt=0)
    estado: str = Field(default="pendiente", max_length=20)
    notas: Optional[str] = None


class CanjeCreate(SQLModel):
    """Esquema para crear canje"""
    id_premio: int


class CanjeRead(CanjeBase):
    """Esquema para leer canje"""
    id: int
    fecha_canje: datetime


class CanjeResumen(SQLModel):
    """Esquema para resumen de canje con detalles del premio"""
    id: int
    fecha_canje: datetime
    puntos_utilizados: int
    estado: str
    notas: Optional[str] = None
    premio_nombre: str
    premio_descripcion: Optional[str] = None


# Validaciones y utilidades

class ValidadorCanjes:
    """Validador para operaciones de canjes"""
    
    @staticmethod
    def puede_canjear(puntos_usuario: int, puntos_requeridos: int) -> bool:
        """Verifica si el usuario tiene suficientes puntos para canjear"""
        return puntos_usuario >= puntos_requeridos
    
    @staticmethod
    def validar_canje(
        puntos_usuario: int,
        premio: CatalogoPremio
    ) -> tuple[bool, Optional[str]]:
        """
        Valida si un canje es posible
        
        Returns:
            Tupla (es_valido, mensaje_error)
        """
        if not premio.activo:
            return False, "El premio no está disponible actualmente"
        
        if puntos_usuario < premio.puntos_requeridos:
            return False, f"Puntos insuficientes. Necesitas {premio.puntos_requeridos} puntos"
        
        return True, None
