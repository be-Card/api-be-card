"""
Servicio de monitoreo de salud de terminales.
Detecta terminales offline y limpia telemetría antigua.
"""
import logging
from datetime import datetime, timedelta

from sqlmodel import Session, select

from app.models.terminal import TerminalRegistro, EquipoTelemetria, TerminalEvento

logger = logging.getLogger(__name__)

# Una terminal se considera offline si no envía heartbeat en 2 minutos
OFFLINE_THRESHOLD_SECONDS = 120

# Retener telemetría por 90 días
TELEMETRY_RETENTION_DAYS = 90

# Retener eventos por 30 días
EVENTS_RETENTION_DAYS = 30


class TerminalHealthService:
    """Monitoreo de salud de terminales"""

    @staticmethod
    def marcar_terminales_offline(session: Session) -> int:
        """
        Revisa terminales que no enviaron heartbeat en el umbral
        y las marca como offline.
        Retorna cantidad de terminales marcadas offline.
        """
        threshold = datetime.utcnow() - timedelta(seconds=OFFLINE_THRESHOLD_SECONDS)

        terminales = session.exec(
            select(TerminalRegistro).where(
                TerminalRegistro.online == True,
                TerminalRegistro.activo == True,
                TerminalRegistro.ultimo_heartbeat < threshold,
            )
        ).all()

        count = 0
        for terminal in terminales:
            terminal.online = False
            session.add(terminal)
            count += 1

        if count > 0:
            session.commit()
            logger.info("Marked %d terminals as offline", count)

        return count

    @staticmethod
    def cleanup_telemetria_antigua(session: Session) -> int:
        """Elimina registros de telemetría más antiguos que el período de retención"""
        cutoff = datetime.utcnow() - timedelta(days=TELEMETRY_RETENTION_DAYS)

        from sqlalchemy import delete as sa_delete
        stmt = sa_delete(EquipoTelemetria).where(EquipoTelemetria.timestamp < cutoff)
        result = session.exec(stmt)
        session.commit()

        count = result.rowcount
        if count > 0:
            logger.info("Cleaned up %d old telemetry records", count)
        return count

    @staticmethod
    def cleanup_eventos_antiguos(session: Session) -> int:
        """Elimina eventos más antiguos que el período de retención"""
        cutoff = datetime.utcnow() - timedelta(days=EVENTS_RETENTION_DAYS)

        from sqlalchemy import delete as sa_delete
        stmt = sa_delete(TerminalEvento).where(TerminalEvento.timestamp < cutoff)
        result = session.exec(stmt)
        session.commit()

        count = result.rowcount
        if count > 0:
            logger.info("Cleaned up %d old event records", count)
        return count

    @staticmethod
    def get_resumen_salud(session: Session, *, tenant_id: int) -> dict:
        """Resumen de salud de terminales de un tenant"""
        terminales = session.exec(
            select(TerminalRegistro).where(
                TerminalRegistro.tenant_id == tenant_id,
                TerminalRegistro.activo == True,
            )
        ).all()

        total = len(terminales)
        online = sum(1 for t in terminales if t.online)
        offline = total - online

        sin_heartbeat = [
            {
                "id_ext": str(t.id_ext),
                "nombre": t.nombre,
                "codigo_terminal": t.codigo_terminal,
                "ultimo_heartbeat": t.ultimo_heartbeat.isoformat() if t.ultimo_heartbeat else None,
            }
            for t in terminales
            if not t.online and t.activo
        ]

        return {
            "total": total,
            "online": online,
            "offline": offline,
            "terminales_offline": sin_heartbeat,
        }
