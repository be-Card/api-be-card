"""
Router para endpoints de terminales MQTT (protegido con JWT)
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import List
from uuid import UUID
import logging

from ..core.database import get_session
from ..core.config import settings
from ..core.tenant import get_current_tenant
from .auth import get_current_user
from ..models.tenant import Tenant
from ..models.user_extended import Usuario
from ..models.terminal import (
    TerminalRegistro,
    TerminalRegistroCreate,
    TerminalRegistroRead,
    TerminalCredencialesRead,
)
from ..services.terminales import TerminalService
from ..services.terminal_health import TerminalHealthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/terminales", tags=["terminales"])


@router.post("/", response_model=TerminalCredencialesRead, status_code=201)
def registrar_terminal(
    data: TerminalRegistroCreate,
    session: Session = Depends(get_session),
    tenant: Tenant = Depends(get_current_tenant),
    current_user: Usuario = Depends(get_current_user),
):
    """Registrar nueva terminal. Devuelve credenciales MQTT (solo visible una vez)."""
    try:
        terminal_read, password_plano = TerminalService.registrar_terminal(
            session,
            data=data,
            tenant_id=tenant.id,
            user_id=current_user.id,
        )
        terminal_obj = session.get(TerminalRegistro, terminal_read.id)
        topics = TerminalService.get_topics_para_terminal(terminal_obj)

        return TerminalCredencialesRead(
            id=terminal_read.id,
            id_ext=terminal_read.id_ext,
            codigo_terminal=terminal_read.codigo_terminal,
            mqtt_username=terminal_read.mqtt_username,
            mqtt_password=password_plano,
            mqtt_client_id=terminal_read.mqtt_client_id,
            mqtt_broker_host=settings.mqtt_broker_host,
            mqtt_broker_port=settings.mqtt_broker_port,
            topics=topics,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=List[TerminalRegistroRead])
def listar_terminales(
    session: Session = Depends(get_session),
    tenant: Tenant = Depends(get_current_tenant),
    current_user: Usuario = Depends(get_current_user),
):
    """Listar terminales del tenant"""
    return TerminalService.get_terminales(session, tenant_id=tenant.id)


@router.get("/health")
def resumen_salud_terminales(
    session: Session = Depends(get_session),
    tenant: Tenant = Depends(get_current_tenant),
    current_user: Usuario = Depends(get_current_user),
):
    """Resumen de salud: cuántas online/offline, cuáles requieren atención"""
    return TerminalHealthService.get_resumen_salud(session, tenant_id=tenant.id)


@router.post("/{id_ext}/rotar-credenciales", response_model=TerminalCredencialesRead)
def rotar_credenciales(
    id_ext: UUID,
    session: Session = Depends(get_session),
    tenant: Tenant = Depends(get_current_tenant),
    current_user: Usuario = Depends(get_current_user),
):
    """Rotar password MQTT de una terminal"""
    terminal = TerminalService.get_terminal_by_id_ext(
        session, tenant_id=tenant.id, terminal_id_ext=id_ext
    )
    if not terminal:
        raise HTTPException(status_code=404, detail="Terminal no encontrada")

    try:
        terminal, password_plano = TerminalService.rotar_credenciales(
            session, terminal_id=terminal.id
        )
        topics = TerminalService.get_topics_para_terminal(terminal)

        return TerminalCredencialesRead(
            id=terminal.id,
            id_ext=str(terminal.id_ext),
            codigo_terminal=terminal.codigo_terminal,
            mqtt_username=terminal.mqtt_username,
            mqtt_password=password_plano,
            mqtt_client_id=terminal.mqtt_client_id,
            mqtt_broker_host=settings.mqtt_broker_host,
            mqtt_broker_port=settings.mqtt_broker_port,
            topics=topics,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{id_ext}", status_code=204)
def desactivar_terminal(
    id_ext: UUID,
    session: Session = Depends(get_session),
    tenant: Tenant = Depends(get_current_tenant),
    current_user: Usuario = Depends(get_current_user),
):
    """Soft delete: desactivar terminal (activo=False)"""
    terminal = TerminalService.get_terminal_by_id_ext(
        session, tenant_id=tenant.id, terminal_id_ext=id_ext
    )
    if not terminal:
        raise HTTPException(status_code=404, detail="Terminal no encontrada")

    terminal.activo = False
    session.add(terminal)
    session.commit()
