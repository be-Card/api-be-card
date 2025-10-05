"""
Modelos de transacciones de puntos y pagos para la API BeCard
"""
from sqlmodel import SQLModel, Field, Relationship, Index, Column
from sqlalchemy import Numeric
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from decimal import Decimal
from enum import Enum

# Importaciones para evitar referencias circulares
if TYPE_CHECKING:
    from .user_extended import Usuario, TipoMetodoPago
    from .sales import Venta
    from .rewards import Canje


class TipoEstadoPago(str, Enum):
    """Estados de pago"""
    APROBADO = "aprobado"
    RECHAZADO = "rechazado"
    PENDIENTE = "pendiente"


class TransaccionPuntos(SQLModel, table=True):
    """
    Auditoría de todos los movimientos de puntos
    Tabla para rastrear todas las ganancias y canjes de puntos
    """
    __tablename__ = "transacciones_puntos"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    id_usuario: int = Field(foreign_key="usuarios.id", index=True)
    puntos_ganados: int = Field(default=0, ge=0, description="Puntos ganados en esta transacción")
    puntos_canjeados: int = Field(default=0, ge=0, description="Puntos canjeados en esta transacción")
    saldo_anterior: int = Field(ge=0, description="Saldo antes de la transacción")
    saldo_posterior: int = Field(ge=0, description="Saldo después de la transacción")
    id_venta: Optional[int] = Field(default=None, description="Venta que generó los puntos")
    id_canje: Optional[int] = Field(
        default=None, 
        foreign_key="canjes.id",
        description="Canje que usó los puntos"
    )
    fecha: datetime = Field(default_factory=datetime.utcnow, index=True)
    descripcion: Optional[str] = Field(default=None, description="Descripción de la transacción")
    tipo_transaccion: str = Field(max_length=20, description="venta, canje, ajuste, bono, referido")
    
    # Relaciones
    usuario: "Usuario" = Relationship(back_populates="transacciones_puntos")
    canje: Optional["Canje"] = Relationship()
    
    # Índices
    __table_args__ = (
        Index('idx_transacciones_puntos_usuario', 'id_usuario'),
        Index('idx_transacciones_puntos_fecha', 'fecha'),
        Index('idx_transacciones_puntos_usuario_fecha', 'id_usuario', 'fecha'),
    )


class Pago(SQLModel, table=True):
    """
    Pagos asociados a ventas
    Registro de transacciones de pago de cada venta
    """
    __tablename__ = "pagos"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    id_venta: int = Field(index=True, description="ID de la venta asociada")
    fecha_venta: datetime = Field(
        index=True,
        description="Fecha de la venta (para FK a tabla particionada)"
    )
    id_metodo_pago: int = Field(foreign_key="tipos_metodo_pago.id", index=True)
    monto: Decimal = Field(
        sa_column=Column(Numeric(10, 2), nullable=False),
        description="Monto del pago"
    )
    estado: TipoEstadoPago = Field(index=True, description="Estado del pago")
    id_transaccion_proveedor: Optional[str] = Field(
        default=None,
        description="ID de transacción del proveedor de pago"
    )
    fecha_pago: datetime = Field(default_factory=datetime.utcnow, index=True)
    fecha_actualizacion: Optional[datetime] = Field(default=None, description="Última actualización del estado")
    motivo_rechazo: Optional[str] = Field(default=None, description="Razón si fue rechazado")
    
    # Relaciones
    metodo_pago: "TipoMetodoPago" = Relationship()
    
    # Índices
    __table_args__ = (
        Index('idx_pagos_venta', 'id_venta'),
        Index('idx_pagos_metodo', 'id_metodo_pago'),
        Index('idx_pagos_estado', 'estado'),
        Index('idx_pagos_fecha', 'fecha_pago'),
        Index('idx_pagos_transaccion', 'id_transaccion_proveedor'),
    )


# Esquemas Pydantic para API

class TransaccionPuntosBase(SQLModel):
    """Esquema base para transacción de puntos"""
    id_usuario: int
    puntos_ganados: int = Field(default=0, ge=0)
    puntos_canjeados: int = Field(default=0, ge=0)
    saldo_anterior: int = Field(ge=0)
    saldo_posterior: int = Field(ge=0)
    id_venta: Optional[int] = None
    id_canje: Optional[int] = None
    descripcion: Optional[str] = None
    tipo_transaccion: str = Field(max_length=20)


class TransaccionPuntosCreate(TransaccionPuntosBase):
    """Esquema para crear transacción de puntos"""
    pass


class TransaccionPuntosRead(TransaccionPuntosBase):
    """Esquema para leer transacción de puntos"""
    id: int
    fecha: datetime


class TransaccionPuntosFilter(SQLModel):
    """Esquema para filtrar transacciones de puntos"""
    fecha_inicio: Optional[datetime] = None
    fecha_fin: Optional[datetime] = None
    solo_ganados: bool = Field(default=False, description="Solo mostrar puntos ganados")
    solo_canjeados: bool = Field(default=False, description="Solo mostrar puntos canjeados")
    limite: int = Field(default=100, le=1000)
    offset: int = Field(default=0, ge=0)


class SaldoPuntos(SQLModel):
    """Esquema para saldo de puntos de un usuario"""
    id_usuario: int
    saldo_actual: int
    total_ganados: int
    total_canjeados: int
    total_transacciones: int
    ultima_actualizacion: datetime


class PagoBase(SQLModel):
    """Esquema base para pago"""
    id_venta: int
    fecha_venta: datetime
    id_metodo_pago: int
    monto: Decimal
    estado: TipoEstadoPago
    id_transaccion_proveedor: Optional[str] = None
    motivo_rechazo: Optional[str] = None


class PagoCreate(SQLModel):
    """Esquema para crear pago"""
    id_venta: int
    fecha_venta: datetime
    id_metodo_pago: int
    monto: Decimal
    id_transaccion_proveedor: Optional[str] = None


class PagoRead(PagoBase):
    """Esquema para leer pago"""
    id: int
    fecha_pago: datetime
    fecha_actualizacion: Optional[datetime] = None


class PagoUpdate(SQLModel):
    """Esquema para actualizar pago"""
    estado: TipoEstadoPago
    id_transaccion_proveedor: Optional[str] = None
    motivo_rechazo: Optional[str] = None


class PagoResumen(SQLModel):
    """Esquema para resumen de pagos"""
    total_pagos: int
    monto_total: Decimal
    aprobados: int
    rechazados: int
    pendientes: int
    fecha_inicio: datetime
    fecha_fin: datetime


# Utilidades para manejo de transacciones

class GestorTransaccionesPuntos:
    """Gestor para operaciones de transacciones de puntos"""
    
    @staticmethod
    def calcular_saldo(transacciones: List[TransaccionPuntos]) -> int:
        """
        Calcula el saldo actual de puntos basado en las transacciones
        
        Args:
            transacciones: Lista de transacciones del usuario
            
        Returns:
            Saldo actual de puntos
        """
        saldo = 0
        for t in transacciones:
            saldo += t.puntos_ganados - t.puntos_canjeados
        return saldo
    
    @staticmethod
    def crear_transaccion_venta(
        id_usuario: int,
        id_venta: int,
        puntos_ganados: int,
        saldo_anterior: int,
        descripcion: Optional[str] = None
    ) -> TransaccionPuntosCreate:
        """Crea una transacción para puntos ganados por venta"""
        if descripcion is None:
            descripcion = f"Puntos ganados por venta #{id_venta}"
        
        return TransaccionPuntosCreate(
            id_usuario=id_usuario,
            puntos_ganados=puntos_ganados,
            puntos_canjeados=0,
            saldo_anterior=saldo_anterior,
            saldo_posterior=saldo_anterior + puntos_ganados,
            id_venta=id_venta,
            tipo_transaccion="venta",
            descripcion=descripcion
        )
    
    @staticmethod
    def crear_transaccion_canje(
        id_usuario: int,
        id_canje: int,
        puntos_canjeados: int,
        saldo_anterior: int,
        descripcion: Optional[str] = None
    ) -> TransaccionPuntosCreate:
        """Crea una transacción para puntos canjeados"""
        if descripcion is None:
            descripcion = f"Puntos canjeados en canje #{id_canje}"
        
        return TransaccionPuntosCreate(
            id_usuario=id_usuario,
            puntos_ganados=0,
            puntos_canjeados=puntos_canjeados,
            saldo_anterior=saldo_anterior,
            saldo_posterior=saldo_anterior - puntos_canjeados,
            id_canje=id_canje,
            tipo_transaccion="canje",
            descripcion=descripcion
        )
