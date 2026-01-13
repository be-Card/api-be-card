"""
Servicio de alertas automáticas para stock de barriles
"""
from sqlmodel import Session, select
from typing import List, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal

from ..models.sales_point import Equipo, TipoBarril, TipoEstadoEquipo
from ..models.beer import Cerveza
from .equipos import EquipoService, EquipoDetailRead


class AlertaStock:
    """Clase para representar una alerta de stock"""
    
    def __init__(
        self,
        equipo_id: int,
        nombre_equipo: str,
        cerveza_nombre: str,
        nivel_actual: int,
        capacidad_barril: int,
        volumen_actual: float,
        tipo_alerta: str,
        prioridad: str,
        mensaje: str
    ):
        self.equipo_id = equipo_id
        self.nombre_equipo = nombre_equipo
        self.cerveza_nombre = cerveza_nombre
        self.nivel_actual = nivel_actual
        self.capacidad_barril = capacidad_barril
        self.volumen_actual = volumen_actual
        self.tipo_alerta = tipo_alerta
        self.prioridad = prioridad
        self.mensaje = mensaje
        self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertir alerta a diccionario"""
        return {
            "equipo_id": self.equipo_id,
            "nombre_equipo": self.nombre_equipo,
            "cerveza_nombre": self.cerveza_nombre,
            "nivel_actual": self.nivel_actual,
            "capacidad_barril": self.capacidad_barril,
            "volumen_actual": self.volumen_actual,
            "tipo_alerta": self.tipo_alerta,
            "prioridad": self.prioridad,
            "mensaje": self.mensaje,
            "timestamp": self.timestamp.isoformat()
        }


class AlertaService:
    """Servicio para gestión de alertas automáticas"""
    
    # Umbrales de alerta
    UMBRAL_CRITICO = 10  # 10% o menos
    UMBRAL_BAJO = 20     # 20% o menos
    UMBRAL_MEDIO = 40    # 40% o menos
    
    @staticmethod
    def verificar_alertas_stock(session: Session) -> List[AlertaStock]:
        """Verificar y generar alertas de stock para todos los equipos activos"""
        alertas = []
        
        # Obtener equipos activos
        equipos = session.exec(
            select(Equipo)
            .join(TipoEstadoEquipo)
            .where(TipoEstadoEquipo.permite_ventas == True)
        ).all()
        
        for equipo in equipos:
            alerta = AlertaService._verificar_alerta_equipo(session, equipo)
            if alerta:
                alertas.append(alerta)
        
        return alertas
    
    @staticmethod
    def _verificar_alerta_equipo(session: Session, equipo: Equipo) -> AlertaStock:
        """Verificar si un equipo específico necesita alerta"""
        
        # Obtener datos del barril
        barril = session.get(TipoBarril, equipo.id_barril)
        if not barril:
            return None
        
        # Calcular porcentaje de nivel
        nivel_porcentaje = EquipoService.get_nivel_barril_porcentaje(
            barril.capacidad,
            equipo.capacidad_actual
        )
        
        # Obtener nombre de cerveza
        cerveza_nombre = "Sin cerveza"
        if equipo.id_cerveza:
            cerveza = session.get(Cerveza, equipo.id_cerveza)
            if cerveza:
                cerveza_nombre = cerveza.nombre
        
        # Determinar tipo de alerta
        tipo_alerta, prioridad, mensaje = AlertaService._determinar_tipo_alerta(
            nivel_porcentaje, 
            equipo.nombre_equipo,
            cerveza_nombre
        )
        
        if tipo_alerta:
            return AlertaStock(
                equipo_id=equipo.id,
                nombre_equipo=equipo.nombre_equipo,
                cerveza_nombre=cerveza_nombre,
                nivel_actual=nivel_porcentaje,
                capacidad_barril=barril.capacidad,
                volumen_actual=float(equipo.capacidad_actual),
                tipo_alerta=tipo_alerta,
                prioridad=prioridad,
                mensaje=mensaje
            )
        
        return None
    
    @staticmethod
    def _determinar_tipo_alerta(
        nivel_porcentaje: int, 
        nombre_equipo: str, 
        cerveza_nombre: str
    ) -> tuple:
        """Determinar el tipo de alerta basado en el nivel de stock"""
        
        if nivel_porcentaje <= AlertaService.UMBRAL_CRITICO:
            return (
                "stock_critico",
                "alta",
                f"🚨 CRÍTICO: {nombre_equipo} tiene solo {nivel_porcentaje}% de {cerveza_nombre}. ¡Cambio de barril urgente!"
            )
        elif nivel_porcentaje <= AlertaService.UMBRAL_BAJO:
            return (
                "stock_bajo",
                "media",
                f"⚠️ BAJO: {nombre_equipo} tiene {nivel_porcentaje}% de {cerveza_nombre}. Preparar cambio de barril."
            )
        elif nivel_porcentaje <= AlertaService.UMBRAL_MEDIO:
            return (
                "stock_medio",
                "baja",
                f"📊 MEDIO: {nombre_equipo} tiene {nivel_porcentaje}% de {cerveza_nombre}. Monitorear nivel."
            )
        
        return None, None, None
    
    @staticmethod
    def get_alertas_activas(session: Session) -> Dict[str, Any]:
        """Obtener resumen de alertas activas"""
        alertas = AlertaService.verificar_alertas_stock(session)
        
        # Clasificar alertas por prioridad
        alertas_criticas = [a for a in alertas if a.prioridad == "alta"]
        alertas_medias = [a for a in alertas if a.prioridad == "media"]
        alertas_bajas = [a for a in alertas if a.prioridad == "baja"]
        
        return {
            "total_alertas": len(alertas),
            "alertas_criticas": {
                "count": len(alertas_criticas),
                "alertas": [a.to_dict() for a in alertas_criticas]
            },
            "alertas_medias": {
                "count": len(alertas_medias),
                "alertas": [a.to_dict() for a in alertas_medias]
            },
            "alertas_bajas": {
                "count": len(alertas_bajas),
                "alertas": [a.to_dict() for a in alertas_bajas]
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def get_equipos_requieren_atencion(session: Session) -> List[EquipoDetailRead]:
        """Obtener equipos que requieren atención inmediata (crítico y bajo)"""
        equipos_criticos = EquipoService.get_equipos_con_stock_bajo(session, AlertaService.UMBRAL_BAJO)
        return equipos_criticos
    
    @staticmethod
    def simular_consumo_barril(
        session: Session, 
        equipo_id: int, 
        litros_consumidos: float
    ) -> Dict[str, Any]:
        """Simular consumo de barril y verificar si genera alertas"""
        
        equipo = session.get(Equipo, equipo_id)
        if not equipo:
            return {"error": "Equipo no encontrado"}
        
        # Calcular nueva capacidad
        nueva_capacidad = max(0, equipo.capacidad_actual - Decimal(str(litros_consumidos)))
        
        # Crear equipo temporal para verificar alertas
        equipo_temp = Equipo(
            id=equipo.id,
            nombre_equipo=equipo.nombre_equipo,
            id_barril=equipo.id_barril,
            capacidad_actual=nueva_capacidad,
            id_cerveza=equipo.id_cerveza,
            id_estado_equipo=equipo.id_estado_equipo
        )
        
        # Verificar si generaría alerta
        alerta = AlertaService._verificar_alerta_equipo(session, equipo_temp)
        
        barril = session.get(TipoBarril, equipo.id_barril)
        nivel_actual = EquipoService.get_nivel_barril_porcentaje(
            barril.capacidad, equipo.capacidad_actual
        )
        nivel_nuevo = EquipoService.get_nivel_barril_porcentaje(
            barril.capacidad, nueva_capacidad
        )
        
        return {
            "equipo_id": equipo_id,
            "nivel_actual": nivel_actual,
            "nivel_despues_consumo": nivel_nuevo,
            "litros_consumidos": litros_consumidos,
            "nueva_capacidad": float(nueva_capacidad),
            "generaria_alerta": alerta is not None,
            "alerta": alerta.to_dict() if alerta else None
        }