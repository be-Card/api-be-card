"""
Servicio de negocio para terminales MQTT
"""
import secrets
import string
import logging
from typing import Optional, List, Tuple
from uuid import UUID
from datetime import datetime

from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.models.terminal import (
    TerminalRegistro,
    TerminalRegistroCreate,
    TerminalRegistroRead,
    TerminalCredencialesRead,
)

logger = logging.getLogger(__name__)


class TerminalService:
    """Servicio de negocio para gestión de terminales"""

    @staticmethod
    def _generar_codigo_terminal() -> str:
        """Genera código único TRM-XXXXXX"""
        chars = string.ascii_uppercase + string.digits
        codigo = "".join(secrets.choice(chars) for _ in range(6))
        return f"TRM-{codigo}"

    @staticmethod
    def _generar_mqtt_password(length: int = 32) -> str:
        """Genera password seguro para MQTT"""
        alphabet = string.ascii_letters + string.digits + "-_"
        return "".join(secrets.choice(alphabet) for _ in range(length))

    @staticmethod
    def _generar_mqtt_client_id(codigo_terminal: str) -> str:
        """Genera client_id MQTT basado en código de terminal"""
        suffix = secrets.token_hex(4)
        return f"becard-{codigo_terminal.lower()}-{suffix}"

    @staticmethod
    def _generar_mqtt_username(tenant_id: int, codigo_terminal: str) -> str:
        """Genera username MQTT"""
        return f"t{tenant_id}-{codigo_terminal.lower()}"

    @staticmethod
    def registrar_terminal(
        session: Session,
        *,
        data: TerminalRegistroCreate,
        tenant_id: int,
        user_id: int,
    ) -> Tuple[TerminalRegistroRead, str]:
        """
        Registra una nueva terminal y genera credenciales MQTT.
        Retorna (terminal_read, password_plano).
        """
        # Generar código único con reintentos
        for _ in range(5):
            codigo = TerminalService._generar_codigo_terminal()
            exists = session.exec(
                select(TerminalRegistro.id).where(
                    TerminalRegistro.tenant_id == tenant_id,
                    TerminalRegistro.codigo_terminal == codigo,
                )
            ).first()
            if not exists:
                break
        else:
            raise ValueError("No se pudo generar un código de terminal único")

        password_plano = TerminalService._generar_mqtt_password()
        mqtt_username = TerminalService._generar_mqtt_username(tenant_id, codigo)
        mqtt_client_id = TerminalService._generar_mqtt_client_id(codigo)

        terminal = TerminalRegistro(
            tenant_id=tenant_id,
            equipo_id=data.equipo_id,
            punto_venta_id=data.punto_venta_id,
            codigo_terminal=codigo,
            nombre=data.nombre,
            descripcion=data.descripcion,
            mqtt_username=mqtt_username,
            mqtt_password_hash=get_password_hash(password_plano),
            mqtt_client_id=mqtt_client_id,
            activo=True,
            online=False,
            hardware_id=data.hardware_id,
            firmware_version=data.firmware_version,
            creado_por=user_id,
        )

        try:
            session.add(terminal)
            session.commit()
            session.refresh(terminal)
        except IntegrityError:
            session.rollback()
            raise ValueError("Error de unicidad al registrar terminal")

        terminal_read = TerminalRegistroRead(
            id=terminal.id,
            id_ext=str(terminal.id_ext),
            tenant_id=terminal.tenant_id,
            equipo_id=terminal.equipo_id,
            punto_venta_id=terminal.punto_venta_id,
            codigo_terminal=terminal.codigo_terminal,
            nombre=terminal.nombre,
            descripcion=terminal.descripcion,
            mqtt_username=terminal.mqtt_username,
            mqtt_client_id=terminal.mqtt_client_id,
            activo=terminal.activo,
            ultimo_heartbeat=terminal.ultimo_heartbeat,
            online=terminal.online,
            hardware_id=terminal.hardware_id,
            firmware_version=terminal.firmware_version,
            ip_address=terminal.ip_address,
            creado_el=terminal.creado_el,
        )

        return terminal_read, password_plano

    @staticmethod
    def autenticar_terminal(
        session: Session,
        *,
        mqtt_username: str,
        mqtt_password: str,
    ) -> Optional[TerminalRegistro]:
        """Valida credenciales MQTT de una terminal. Retorna la terminal o None."""
        terminal = session.exec(
            select(TerminalRegistro).where(
                TerminalRegistro.mqtt_username == mqtt_username,
                TerminalRegistro.activo == True,
            )
        ).first()

        if terminal is None:
            return None

        if not verify_password(mqtt_password, terminal.mqtt_password_hash):
            return None

        return terminal

    @staticmethod
    def registrar_heartbeat(
        session: Session,
        *,
        terminal_id: int,
        ip_address: Optional[str] = None,
    ) -> None:
        """Actualiza ultimo_heartbeat y marca online"""
        terminal = session.get(TerminalRegistro, terminal_id)
        if terminal is None:
            return
        terminal.ultimo_heartbeat = datetime.utcnow()
        terminal.online = True
        if ip_address:
            terminal.ip_address = ip_address
        session.add(terminal)
        session.commit()

    @staticmethod
    def marcar_offline(session: Session, *, terminal_id: int) -> None:
        """Marca la terminal como offline"""
        terminal = session.get(TerminalRegistro, terminal_id)
        if terminal is None:
            return
        terminal.online = False
        session.add(terminal)
        session.commit()

    @staticmethod
    def rotar_credenciales(
        session: Session,
        *,
        terminal_id: int,
    ) -> Tuple[TerminalRegistro, str]:
        """Genera nuevo password MQTT. Retorna (terminal, password_plano)."""
        terminal = session.get(TerminalRegistro, terminal_id)
        if terminal is None:
            raise ValueError("Terminal no encontrada")

        password_plano = TerminalService._generar_mqtt_password()
        terminal.mqtt_password_hash = get_password_hash(password_plano)
        session.add(terminal)
        session.commit()
        session.refresh(terminal)

        return terminal, password_plano

    @staticmethod
    def get_terminales(
        session: Session,
        *,
        tenant_id: int,
    ) -> List[TerminalRegistroRead]:
        """Lista terminales activas de un tenant"""
        terminales = session.exec(
            select(TerminalRegistro).where(
                TerminalRegistro.tenant_id == tenant_id,
                TerminalRegistro.activo == True,
            ).order_by(TerminalRegistro.nombre)
        ).all()

        return [
            TerminalRegistroRead(
                id=t.id,
                id_ext=str(t.id_ext),
                tenant_id=t.tenant_id,
                equipo_id=t.equipo_id,
                punto_venta_id=t.punto_venta_id,
                codigo_terminal=t.codigo_terminal,
                nombre=t.nombre,
                descripcion=t.descripcion,
                mqtt_username=t.mqtt_username,
                mqtt_client_id=t.mqtt_client_id,
                activo=t.activo,
                ultimo_heartbeat=t.ultimo_heartbeat,
                online=t.online,
                hardware_id=t.hardware_id,
                firmware_version=t.firmware_version,
                ip_address=t.ip_address,
                creado_el=t.creado_el,
            )
            for t in terminales
        ]

    @staticmethod
    def get_terminal_by_id_ext(
        session: Session,
        *,
        tenant_id: int,
        terminal_id_ext: UUID,
    ) -> Optional[TerminalRegistro]:
        """Obtiene terminal por id_ext y tenant"""
        return session.exec(
            select(TerminalRegistro).where(
                TerminalRegistro.id_ext == terminal_id_ext,
                TerminalRegistro.tenant_id == tenant_id,
                TerminalRegistro.activo == True,
            )
        ).first()

    @staticmethod
    def get_topics_para_terminal(terminal: TerminalRegistro) -> dict:
        """Retorna dict de topics MQTT asignados a la terminal"""
        prefix = settings.mqtt_topic_prefix
        t_ext = str(terminal.id_ext)
        # Usamos tenant_id como slug simplificado
        tenant_slug = str(terminal.tenant_id)
        base = f"{prefix}/{tenant_slug}/{t_ext}"
        return {
            "telemetry_temperature": f"{base}/telemetry/temperature",
            "telemetry_barrel_level": f"{base}/telemetry/barrel_level",
            "heartbeat": f"{base}/heartbeat",
            "event_session_completed": f"{base}/event/session_completed",
            "command_lock": f"{base}/command/lock",
            "command_update_config": f"{base}/command/update_config",
        }
