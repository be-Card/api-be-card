"""
Modelos de sistema de puntos y conversión para la API BeCard
"""
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import Numeric
from typing import Optional
from datetime import datetime
from decimal import Decimal


class ReglaConversionPuntos(SQLModel, table=True):
    """
    Reglas de conversión de puntos por consumo
    Define cómo se convierten los montos gastados en puntos
    """
    __tablename__ = "reglas_conversion_puntos"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    monto_minimo: Decimal = Field(
        sa_column=Column(Numeric(10, 2), nullable=False),
        description="Monto mínimo de compra para aplicar la conversión"
    )
    puntos_por_peso: Decimal = Field(
        sa_column=Column(Numeric(6, 2), nullable=False),
        description="Cantidad de puntos otorgados por cada peso gastado"
    )
    activo: bool = Field(default=False, index=True)
    fecha_inicio: datetime = Field(default_factory=datetime.utcnow)
    fecha_fin: Optional[datetime] = Field(default=None)
    descripcion: Optional[str] = Field(default=None, description="Descripción de la regla")
    prioridad: int = Field(default=1, description="Prioridad para múltiples reglas")


# Esquemas Pydantic para API

class ReglaConversionPuntosBase(SQLModel):
    """Esquema base para regla de conversión de puntos"""
    monto_minimo: Decimal
    puntos_por_peso: Decimal
    activo: bool = Field(default=False)
    fecha_inicio: datetime = Field(default_factory=datetime.utcnow)
    fecha_fin: Optional[datetime] = None
    descripcion: Optional[str] = None
    prioridad: int = Field(default=1)


class ReglaConversionPuntosCreate(ReglaConversionPuntosBase):
    """Esquema para crear regla de conversión de puntos"""
    pass


class ReglaConversionPuntosRead(ReglaConversionPuntosBase):
    """Esquema para leer regla de conversión de puntos"""
    id: int


class ReglaConversionPuntosUpdate(SQLModel):
    """Esquema para actualizar regla de conversión de puntos"""
    monto_minimo: Optional[Decimal] = None
    puntos_por_peso: Optional[Decimal] = None
    activo: Optional[bool] = None
    fecha_fin: Optional[datetime] = None
    descripcion: Optional[str] = None
    prioridad: Optional[int] = None


class CalculoPuntos(SQLModel):
    """Esquema para resultado de cálculo de puntos"""
    monto_compra: Decimal
    puntos_ganados: int
    regla_aplicada: Optional[int] = Field(description="ID de la regla aplicada")
    puntos_por_peso_aplicado: Decimal


class ConsultaPuntos(SQLModel):
    """Esquema para consultar puntos por monto"""
    monto: Decimal


# Funciones auxiliares para cálculo de puntos

class CalculadoraPuntos:
    """
    Clase auxiliar para cálculo de puntos por consumo
    """
    
    @staticmethod
    def calcular_puntos(
        monto: Decimal,
        reglas: list[ReglaConversionPuntos]
    ) -> CalculoPuntos:
        """
        Calcula los puntos ganados por un monto específico
        
        Args:
            monto: Monto de la compra
            reglas: Lista de reglas de conversión activas
            
        Returns:
            CalculoPuntos con el resultado del cálculo
        """
        # Filtrar reglas activas y aplicables
        reglas_aplicables = [
            regla for regla in reglas
            if regla.activo and monto >= regla.monto_minimo
        ]
        
        if not reglas_aplicables:
            return CalculoPuntos(
                monto_compra=monto,
                puntos_ganados=0,
                regla_aplicada=None,
                puntos_por_peso_aplicado=Decimal('0.00')
            )
        
        # Usar la regla con mayor puntos por peso
        mejor_regla = max(reglas_aplicables, key=lambda r: r.puntos_por_peso)
        
        # Calcular puntos (redondear hacia abajo)
        puntos_ganados = int(monto * mejor_regla.puntos_por_peso)
        
        return CalculoPuntos(
            monto_compra=monto,
            puntos_ganados=puntos_ganados,
            regla_aplicada=mejor_regla.id,
            puntos_por_peso_aplicado=mejor_regla.puntos_por_peso
        )
    
    @staticmethod
    def obtener_regla_activa_optima() -> Optional[ReglaConversionPuntos]:
        """
        Obtiene la regla activa con mejor conversión
        
        Esta función debe implementarse en el servicio correspondiente
        con acceso a la base de datos.
        """
        # Placeholder - implementar en el servicio
        return None
    
    @staticmethod
    def validar_regla(regla: ReglaConversionPuntosCreate) -> list[str]:
        """
        Valida una regla de conversión de puntos
        
        Returns:
            Lista de errores de validación (vacía si es válida)
        """
        errores = []
        
        if regla.monto_minimo <= 0:
            errores.append("El monto mínimo debe ser mayor a 0")
        
        if regla.puntos_por_peso <= 0:
            errores.append("Los puntos por peso deben ser mayor a 0")
        
        if regla.puntos_por_peso > 100:
            errores.append("Los puntos por peso no pueden ser mayor a 100")
        
        return errores


# Constantes para el sistema de puntos

class ConfiguracionPuntos:
    """Configuración del sistema de puntos"""
    
    # Valores por defecto
    MONTO_MINIMO_DEFAULT = Decimal('10.00')
    PUNTOS_POR_PESO_DEFAULT = Decimal('1.00')
    
    # Límites
    MONTO_MINIMO_MAX = Decimal('1000.00')
    PUNTOS_POR_PESO_MAX = Decimal('100.00')
    
    # Mensajes
    MENSAJE_PUNTOS_GANADOS = "¡Felicitaciones! Has ganado {puntos} puntos por tu compra de ${monto}"
    MENSAJE_SIN_PUNTOS = "Esta compra no genera puntos. Monto mínimo requerido: ${monto_minimo}"