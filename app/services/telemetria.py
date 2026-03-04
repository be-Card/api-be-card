"""
Servicio de negocio para telemetría y eventos de terminales.
Notifica al WebSocket cuando hay nuevos datos.
"""
import asyncio
import logging
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

from sqlmodel import Session, select

from app.models.terminal import (
    EquipoTelemetria,
    TerminalEvento,
    EquipoTelemetriaRead,
    TerminalEventoRead,
)
from app.models.sales_point import Equipo

logger = logging.getLogger(__name__)


def _try_notify_ws(tenant_id: int, data: dict):
    """Intenta notificar al WebSocket manager (fire-and-forget)."""
    try:
        from app.routers.ws_telemetria import notify_telemetry
        loop = asyncio.get_running_loop()
        loop.create_task(notify_telemetry(tenant_id, data))
    except RuntimeError:
        # No hay event loop corriendo (sync context, tests, etc.)
        pass
    except Exception as e:
        logger.warning("Failed to notify WebSocket: %s", e)


# Mapeo tipo → unidad válida (evita combinaciones incoherentes)
VALID_TYPE_UNIT = {
    "temperature": "celsius",
    "barrel_level": "liters",
    "flow_rate": "ml_per_sec",
}

# Rangos válidos de telemetría para detectar lecturas erróneas
VALID_RANGES = {
    "temperature": (-20.0, 80.0),      # °C
    "barrel_level": (0.0, 1000.0),     # litros
    "flow_rate": (0.0, 500.0),         # ml/seg
}


class TelemetriaService:
    """Servicio de negocio para telemetría de equipos"""

    @staticmethod
    def _validar_lectura(tipo: str, valor: float, unidad: str) -> None:
        """Valida tipo, unidad (par correcto) y valor en rango aceptable"""
        if tipo not in VALID_TYPE_UNIT:
            raise ValueError(f"Tipo de telemetría inválido: {tipo}")

        expected_unit = VALID_TYPE_UNIT[tipo]
        if unidad != expected_unit:
            raise ValueError(
                f"Unidad '{unidad}' no corresponde al tipo '{tipo}' (esperada: '{expected_unit}')"
            )

        min_val, max_val = VALID_RANGES[tipo]
        if valor < min_val or valor > max_val:
            raise ValueError(f"Valor {valor} fuera de rango [{min_val}, {max_val}] para {tipo}")

    @staticmethod
    def registrar_lectura(
        session: Session,
        *,
        tenant_id: int,
        terminal_id: int,
        equipo_id: int,
        tipo: str,
        valor: float,
        unidad: str,
        timestamp: Optional[datetime] = None,
    ) -> EquipoTelemetriaRead:
        """Persiste lectura de telemetría y actualiza campo actual en Equipo"""
        TelemetriaService._validar_lectura(tipo, valor, unidad)
        ts = timestamp or datetime.utcnow()

        lectura = EquipoTelemetria(
            tenant_id=tenant_id,
            terminal_id=terminal_id,
            equipo_id=equipo_id,
            tipo=tipo,
            valor=valor,
            unidad=unidad,
            timestamp=ts,
        )
        session.add(lectura)

        # Actualizar campo actual en equipo
        equipo = session.get(Equipo, equipo_id)
        if equipo:
            if tipo == "temperature":
                equipo.temperatura_actual = Decimal(str(round(valor, 2)))
                session.add(equipo)
            elif tipo == "barrel_level":
                equipo.capacidad_actual = int(valor)
                session.add(equipo)
        else:
            logger.warning("Equipo %d no encontrado al actualizar telemetría", equipo_id)

        session.commit()
        session.refresh(lectura)

        result = EquipoTelemetriaRead(
            id=lectura.id,
            id_ext=str(lectura.id_ext),
            terminal_id=lectura.terminal_id,
            equipo_id=lectura.equipo_id,
            tipo=lectura.tipo,
            valor=lectura.valor,
            unidad=lectura.unidad,
            timestamp=lectura.timestamp,
        )

        _try_notify_ws(tenant_id, {
            "type": "telemetry",
            "equipo_id": equipo_id,
            "terminal_id": terminal_id,
            "tipo": tipo,
            "valor": valor,
            "unidad": unidad,
            "timestamp": ts.isoformat(),
        })

        return result

    @staticmethod
    def registrar_evento(
        session: Session,
        *,
        tenant_id: int,
        terminal_id: int,
        tipo_evento: str,
        payload: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> TerminalEventoRead:
        """Persiste evento de terminal"""
        ts = timestamp or datetime.utcnow()

        evento = TerminalEvento(
            tenant_id=tenant_id,
            terminal_id=terminal_id,
            tipo_evento=tipo_evento,
            payload=payload,
            timestamp=ts,
        )
        session.add(evento)
        session.commit()
        session.refresh(evento)

        result = TerminalEventoRead(
            id=evento.id,
            id_ext=str(evento.id_ext),
            terminal_id=evento.terminal_id,
            tipo_evento=evento.tipo_evento,
            payload=evento.payload,
            timestamp=evento.timestamp,
        )

        if tipo_evento in ("heartbeat", "connect", "disconnect"):
            _try_notify_ws(tenant_id, {
                "type": "terminal_status",
                "terminal_id": terminal_id,
                "evento": tipo_evento,
                "timestamp": ts.isoformat(),
            })

        return result

    @staticmethod
    def get_historial_telemetria(
        session: Session,
        *,
        tenant_id: int,
        equipo_id: int,
        tipo: Optional[str] = None,
        desde: Optional[datetime] = None,
        hasta: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[EquipoTelemetriaRead]:
        """Consulta historial de telemetría con filtros (aislado por tenant)"""
        stmt = select(EquipoTelemetria).where(
            EquipoTelemetria.tenant_id == tenant_id,
            EquipoTelemetria.equipo_id == equipo_id,
        )

        if tipo:
            stmt = stmt.where(EquipoTelemetria.tipo == tipo)
        if desde:
            stmt = stmt.where(EquipoTelemetria.timestamp >= desde)
        if hasta:
            stmt = stmt.where(EquipoTelemetria.timestamp <= hasta)

        stmt = stmt.order_by(EquipoTelemetria.timestamp.desc()).limit(limit)

        lecturas = session.exec(stmt).all()

        return [
            EquipoTelemetriaRead(
                id=l.id,
                id_ext=str(l.id_ext),
                terminal_id=l.terminal_id,
                equipo_id=l.equipo_id,
                tipo=l.tipo,
                valor=l.valor,
                unidad=l.unidad,
                timestamp=l.timestamp,
            )
            for l in lecturas
        ]
