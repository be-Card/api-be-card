"""
Modelos de ventas y transacciones para la API BeCard
Incluye soporte para particionamiento por fecha
"""
from sqlmodel import SQLModel, Field, Relationship, Index, Column
from sqlalchemy import Integer, Numeric
from typing import Optional, TYPE_CHECKING
from datetime import datetime
from decimal import Decimal

# Importaciones para evitar referencias circulares
if TYPE_CHECKING:
    from .user_extended import Usuario
    from .beer import Cerveza
    from .sales_point import Equipo


class Venta(SQLModel, table=True):
    """
    Modelo de ventas con soporte para particionamiento por fecha
    
    Nota: El particionamiento se maneja a nivel de base de datos.
    SQLModel/SQLAlchemy no tiene soporte nativo para particionamiento,
    pero puede trabajar con tablas particionadas existentes.
    """
    __tablename__ = "ventas"
    
    id: Optional[int] = Field(sa_column=Column(Integer, primary_key=True, autoincrement=True), default=None)
    id_ext: str = Field(unique=True, index=True)
    fecha_hora: datetime = Field(default_factory=datetime.utcnow, index=True)
    cantidad_ml: int = Field(gt=0, description="Cantidad en mililitros")
    monto_total: Decimal = Field(
        sa_column=Column(Numeric(10, 2), nullable=False),
        description="Monto total de la venta"
    )
    descuento_aplicado: Decimal = Field(
        default=0,
        sa_column=Column(Numeric(10, 2), nullable=False, server_default="0"),
        description="Descuento aplicado a la venta"
    )
    notas: Optional[str] = Field(default=None, description="Notas adicionales")
    
    # Claves foráneas
    id_usuario: Optional[int] = Field(foreign_key="usuarios.id", default=None, index=True)
    id_cerveza: Optional[int] = Field(foreign_key="cervezas.id", default=None, index=True)
    id_equipo: Optional[int] = Field(foreign_key="equipos.id", default=None, index=True)
    
    # Relaciones
    usuario: Optional["Usuario"] = Relationship(back_populates="ventas")
    cerveza: Optional["Cerveza"] = Relationship(back_populates="ventas")
    equipo: Optional["Equipo"] = Relationship(back_populates="ventas")
    
    # Índices para optimización de consultas
    __table_args__ = (
        Index('idx_ventas_usuario', 'id_usuario'),
        Index('idx_ventas_cerveza', 'id_cerveza'),
        Index('idx_ventas_equipo', 'id_equipo'),
        Index('idx_ventas_fecha_hora', 'fecha_hora'),
        Index('idx_ventas_fecha_usuario', 'fecha_hora', 'id_usuario'),
        Index('idx_ventas_fecha_cerveza', 'fecha_hora', 'id_cerveza'),
    )


# Esquemas Pydantic para API

class VentaBase(SQLModel):
    """Esquema base para venta"""
    cantidad_ml: int = Field(gt=0)
    monto_total: Decimal
    descuento_aplicado: Decimal = Decimal("0")
    notas: Optional[str] = None
    id_usuario: Optional[int] = None
    id_cerveza: Optional[int] = None
    id_equipo: Optional[int] = None


class VentaCreate(VentaBase):
    """Esquema para crear venta"""
    pass


class VentaRead(VentaBase):
    """Esquema para leer venta"""
    id: int
    id_ext: str
    fecha_hora: datetime


class VentaUpdate(SQLModel):
    """Esquema para actualizar venta (limitado)"""
    cantidad_ml: Optional[int] = Field(default=None, gt=0)
    monto_total: Optional[Decimal] = None
    descuento_aplicado: Optional[Decimal] = None
    notas: Optional[str] = None


class VentaFilter(SQLModel):
    """Esquema para filtrar ventas"""
    fecha_inicio: Optional[datetime] = None
    fecha_fin: Optional[datetime] = None
    id_usuario: Optional[int] = None
    id_cerveza: Optional[int] = None
    id_equipo: Optional[int] = None
    limite: int = Field(default=100, le=1000)
    offset: int = Field(default=0, ge=0)


class VentaStats(SQLModel):
    """Esquema para estadísticas de ventas"""
    total_ventas: int
    total_monto: Decimal
    total_cantidad_ml: int
    fecha_inicio: datetime
    fecha_fin: datetime


class VentaResumen(SQLModel):
    """Esquema para resumen de ventas por período"""
    periodo: str  # 'diario', 'semanal', 'mensual'
    fecha: datetime
    total_ventas: int
    total_monto: Decimal
    total_cantidad_ml: int
    cerveza_mas_vendida: Optional[str] = None


# Funciones auxiliares para manejo de particiones

class ParticionVentas:
    """
    Clase auxiliar para manejo de particiones de ventas
    
    Nota: Estas funciones son para referencia. El particionamiento
    real se debe configurar a nivel de base de datos PostgreSQL.
    """
    
    @staticmethod
    def generar_nombre_particion(fecha: datetime) -> str:
        """Genera el nombre de la partición basado en la fecha"""
        return f"ventas_{fecha.year}_{fecha.month:02d}"
    
    @staticmethod
    def obtener_rango_particion(fecha: datetime) -> tuple[str, str]:
        """Obtiene el rango de fechas para una partición mensual"""
        año = fecha.year
        mes = fecha.month
        
        # Primer día del mes
        fecha_inicio = f"{año}-{mes:02d}-01"
        
        # Primer día del siguiente mes
        if mes == 12:
            fecha_fin = f"{año + 1}-01-01"
        else:
            fecha_fin = f"{año}-{mes + 1:02d}-01"
        
        return fecha_inicio, fecha_fin
    
    @staticmethod
    def crear_sql_particion(fecha: datetime) -> str:
        """
        Genera SQL para crear una nueva partición
        
        Ejemplo de uso en migraciones o scripts de mantenimiento
        """
        nombre_particion = ParticionVentas.generar_nombre_particion(fecha)
        fecha_inicio, fecha_fin = ParticionVentas.obtener_rango_particion(fecha)
        
        return f"""
        CREATE TABLE {nombre_particion} PARTITION OF ventas
        FOR VALUES FROM ('{fecha_inicio}') TO ('{fecha_fin}');
        """


# Configuración de índices adicionales para particiones
INDICES_PARTICION = [
    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_{tabla}_usuario ON {tabla}(id_usuario);",
    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_{tabla}_cerveza ON {tabla}(id_cerveza);",
    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_{tabla}_equipo ON {tabla}(id_equipo);",
    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_{tabla}_fecha_hora ON {tabla}(fecha_hora DESC);",
    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_{tabla}_fecha_usuario ON {tabla}(fecha_hora, id_usuario);",
    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_{tabla}_fecha_cerveza ON {tabla}(fecha_hora, id_cerveza);",
]
