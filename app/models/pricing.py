"""
Modelos de reglas de precios y alcances para la API BeCard
"""
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from decimal import Decimal
from .base import BaseModel, TipoPrioridadRegla, TipoAlcanceRegla

# Importaciones para evitar referencias circulares
if TYPE_CHECKING:
    from .user_extended import Usuario
    from .beer import Cerveza
    from .sales_point import PuntoVenta, Equipo


class TipoAlcanceReglaDePrecio(BaseModel, table=True):
    """Tipos de alcance para reglas de precio (por equipo, por punto de venta, por cerveza, etc.)"""
    __tablename__ = "tipo_alcance_regla_de_precio"
    
    tipo_regla: str = Field(max_length=50)
    
    # Relaciones
    reglas_precio: List["ReglaDePrecio"] = Relationship(back_populates="tipo_alcance")


class ReglaDePrecio(BaseModel, table=True):
    """Reglas de precio con diferentes alcances y prioridades"""
    __tablename__ = "reglas_de_precio"
    
    nombre: str = Field(max_length=50)
    descripcion: Optional[str] = Field(default=None, description="Descripción de la regla")
    precio: Optional[Decimal] = Field(
        default=None,
        max_digits=10,
        decimal_places=2,
        description="Precio fijo (si aplica)"
    )
    esta_activo: bool = Field(default=False, index=True)
    prioridad: TipoPrioridadRegla = Field(default=TipoPrioridadRegla.BAJA, index=True)
    multiplicador: Decimal = Field(
        max_digits=5,
        decimal_places=2,
        description="Multiplicador para cálculo de precio"
    )
    fecha_hora_inicio: datetime = Field(default_factory=datetime.utcnow, index=True)
    fecha_hora_fin: Optional[datetime] = Field(default=None, index=True)
    creado_por: int = Field(foreign_key="usuarios.id")
    creado_el: datetime = Field(default_factory=datetime.utcnow)
    dias_semana: Optional[str] = Field(default=None, description="Días de la semana aplicables (JSON array)")
    
    # Relaciones
    tipo_alcance: Optional[TipoAlcanceReglaDePrecio] = Relationship(back_populates="reglas_precio")
    creador: "Usuario" = Relationship()
    alcances: List["ReglaDePrecioAlcance"] = Relationship(back_populates="regla_precio")
    # DEPRECATED: Mantener para compatibilidad
    entidades: List["ReglaDePrecioEntidad"] = Relationship(back_populates="regla_precio")
    
    def esta_vigente(self, fecha: Optional[datetime] = None) -> bool:
        """Verifica si la regla está vigente en una fecha específica"""
        if fecha is None:
            fecha = datetime.utcnow()
        return (
            self.esta_activo and
            self.fecha_hora_inicio <= fecha <= self.fecha_hora_fin
        )


class ReglaDePrecioAlcance(SQLModel, table=True):
    """
    Define el alcance de una regla de precio (cerveza, punto de venta o equipo)
    Según el schema SQL mejorado
    """
    __tablename__ = "reglas_de_precios_alcance"
    
    id_regla_de_precio: int = Field(foreign_key="reglas_de_precio.id", primary_key=True)
    tipo_alcance: TipoAlcanceRegla = Field(primary_key=True)
    id_entidad: int = Field(primary_key=True, description="ID de cerveza, punto de venta o equipo")
    
    # Relaciones
    regla_precio: ReglaDePrecio = Relationship(back_populates="alcances")


# DEPRECATED: Mantener para compatibilidad con código existente
class ReglaDePrecioEntidad(SQLModel, table=True):
    """
    DEPRECATED: Usar ReglaDePrecioAlcance
    Entidades específicas afectadas por reglas de precio
    Solo se llena el campo correspondiente al tipo de alcance, el resto queda NULL
    """
    __tablename__ = "reglas_de_precio_entidades"
    
    id_regla_de_precio: int = Field(foreign_key="reglas_de_precio.id", primary_key=True)
    id_cerveza: Optional[int] = Field(foreign_key="cervezas.id", default=None, primary_key=True)
    id_punto_de_venta: Optional[int] = Field(foreign_key="puntos_de_venta.id", default=None, primary_key=True)
    id_equipo: Optional[int] = Field(foreign_key="equipos.id", default=None, primary_key=True)
    
    # Relaciones
    regla_precio: ReglaDePrecio = Relationship(back_populates="entidades")
    cerveza: Optional["Cerveza"] = Relationship(back_populates="reglas_precio")
    punto_venta: Optional["PuntoVenta"] = Relationship(back_populates="reglas_precio")
    equipo: Optional["Equipo"] = Relationship(back_populates="reglas_precio")


# Esquemas Pydantic para API

class TipoAlcanceReglaDePrecioBase(SQLModel):
    """Esquema base para tipo de alcance de regla de precio"""
    tipo_regla: str = Field(max_length=50)


class TipoAlcanceReglaDePrecioCreate(TipoAlcanceReglaDePrecioBase):
    """Esquema para crear tipo de alcance de regla de precio"""
    pass


class TipoAlcanceReglaDePrecioRead(TipoAlcanceReglaDePrecioBase):
    """Esquema para leer tipo de alcance de regla de precio"""
    id: int
    id_ext: str


class ReglaDePrecioBase(SQLModel):
    """Esquema base para regla de precio"""
    nombre: str = Field(max_length=50)
    descripcion: Optional[str] = None
    precio: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=2)
    esta_activo: bool = Field(default=False)
    prioridad: TipoPrioridadRegla = Field(default=TipoPrioridadRegla.BAJA)
    multiplicador: Decimal = Field(max_digits=5, decimal_places=2)
    fecha_hora_inicio: datetime
    fecha_hora_fin: Optional[datetime] = None
    dias_semana: Optional[str] = None


class ReglaDePrecioCreate(ReglaDePrecioBase):
    """Esquema para crear regla de precio"""
    # Entidades afectadas (solo una debe estar presente según el tipo de alcance)
    cervezas_ids: Optional[List[int]] = Field(default=None)
    puntos_venta_ids: Optional[List[int]] = Field(default=None)
    equipos_ids: Optional[List[int]] = Field(default=None)


class ReglaDePrecioRead(ReglaDePrecioBase):
    """Esquema para leer regla de precio"""
    id: int
    id_ext: str
    creado_por: int
    creado_el: datetime
    vigente: bool = Field(description="Si la regla está vigente actualmente")


class ReglaDePrecioUpdate(SQLModel):
    """Esquema para actualizar regla de precio"""
    nombre: Optional[str] = Field(default=None, max_length=50)
    descripcion: Optional[str] = None
    precio: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=2)
    esta_activo: Optional[bool] = None
    prioridad: Optional[TipoPrioridadRegla] = None
    multiplicador: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=2)
    fecha_hora_inicio: Optional[datetime] = None
    fecha_hora_fin: Optional[datetime] = None
    dias_semana: Optional[str] = None
    # Entidades afectadas
    cervezas_ids: Optional[List[int]] = None
    puntos_venta_ids: Optional[List[int]] = None
    equipos_ids: Optional[List[int]] = None


class ReglaDePrecioEntidadRead(SQLModel):
    """Esquema para leer entidad de regla de precio"""
    id_regla_de_precio: int
    id_cerveza: Optional[int] = None
    id_punto_de_venta: Optional[int] = None
    id_equipo: Optional[int] = None


class CalculoPrecio(SQLModel):
    """Esquema para resultado de cálculo de precio"""
    precio_base: Decimal
    precio_final: Decimal
    reglas_aplicadas: List[str] = Field(description="Nombres de las reglas aplicadas")
    multiplicador_total: Decimal = Field(description="Multiplicador total aplicado")
    descuento_aplicado: Optional[Decimal] = Field(default=None)


class ConsultaPrecio(SQLModel):
    """Esquema para consultar precio de una cerveza"""
    id_cerveza: int
    id_equipo: Optional[int] = None
    id_punto_venta: Optional[int] = None
    fecha_consulta: Optional[datetime] = None
    cantidad: int = Field(default=1, gt=0)


# Funciones auxiliares para cálculo de precios

class CalculadoraPrecios:
    """
    Clase auxiliar para cálculo de precios con reglas
    """
    
    @staticmethod
    def aplicar_reglas(
        precio_base: Decimal,
        reglas: List[ReglaDePrecio],
        fecha: Optional[datetime] = None
    ) -> CalculoPrecio:
        """
        Aplica las reglas de precio en orden de prioridad
        """
        if fecha is None:
            fecha = datetime.utcnow()
        
        # Filtrar reglas vigentes
        reglas_vigentes = [
            regla for regla in reglas 
            if regla.esta_vigente(fecha)
        ]
        
        # Ordenar por prioridad (alta > media > baja)
        orden_prioridad = {
            TipoPrioridadRegla.ALTA: 3,
            TipoPrioridadRegla.MEDIA: 2,
            TipoPrioridadRegla.BAJA: 1
        }
        
        reglas_ordenadas = sorted(
            reglas_vigentes,
            key=lambda r: orden_prioridad[r.prioridad],
            reverse=True
        )
        
        precio_final = precio_base
        multiplicador_total = 1
        reglas_aplicadas = []
        
        for regla in reglas_ordenadas:
            if regla.precio is not None:
                # Precio fijo
                precio_final = regla.precio
            else:
                # Aplicar multiplicador
                multiplicador_total *= regla.multiplicador
                precio_final = precio_base * multiplicador_total
            
            reglas_aplicadas.append(regla.nombre)
        
        descuento = precio_base - precio_final if precio_final < precio_base else None
        
        return CalculoPrecio(
            precio_base=precio_base,
            precio_final=precio_final,
            reglas_aplicadas=reglas_aplicadas,
            multiplicador_total=multiplicador_total,
            descuento_aplicado=descuento
        )
    
    @staticmethod
    def obtener_reglas_aplicables(
        id_cerveza: Optional[int] = None,
        id_equipo: Optional[int] = None,
        id_punto_venta: Optional[int] = None
    ) -> List[int]:
        """
        Obtiene los IDs de las reglas aplicables para una consulta específica
        
        Esta función debe implementarse en el servicio correspondiente
        con acceso a la base de datos.
        """
        # Placeholder - implementar en el servicio
        return []