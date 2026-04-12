"""
Router para webhooks de pasarelas de pago.
Endpoints públicos (sin JWT) — validados por firma del proveedor.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from decimal import Decimal
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, Request
from sqlmodel import Session, select

from app.core.config import settings
from app.core.database import engine
from app.models.device_session import DeviceSession
from app.models.points import CalculadoraPuntos, ReglaConversionPuntos
from app.models.sales import Venta
from app.models.sales_point import Equipo, PuntoVenta
from app.models.terminal_checkout import TerminalCheckoutSession
from app.models.transactions import Pago, TipoEstadoPago, TransaccionPuntos
from app.models.user_extended import UsuarioNivel
from app.services.terminal_checkout import TerminalCheckoutService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/mercadopago")
async def mercadopago_webhook(request: Request):
    """
    Webhook de MercadoPago. Público, sin JWT.
    Valida firma, parsea pago, actualiza Pago/DeviceSession, calcula puntos.
    """
    body = await request.body()
    headers = dict(request.headers)

    try:
        from app.services.payment_gateway import get_payment_gateway

        gateway = get_payment_gateway("mercadopago")
    except ValueError:
        logger.error("MercadoPago gateway no configurado")
        raise HTTPException(status_code=500, detail="Gateway no configurado")

    # Validar firma
    if not gateway.verify_webhook_signature(headers, body):
        logger.warning("MP webhook: firma inválida")
        raise HTTPException(status_code=401, detail="Firma inválida")

    # Parsear datos del webhook
    try:
        payment_data = gateway.parse_webhook(headers, body)
    except ValueError as e:
        logger.info("MP webhook ignorado: %s", e)
        return {"ok": True, "ignored": True}

    external_ref = payment_data.external_reference
    if not external_ref:
        logger.warning("MP webhook sin external_reference")
        return {"ok": True, "ignored": True}

    # Buscar el pago en nuestra BD
    with Session(engine) as db:
        try:
            external_ref_uuid = UUID(external_ref)
        except ValueError:
            external_ref_uuid = None

        checkout_session = db.exec(
            select(TerminalCheckoutSession).where(
                TerminalCheckoutSession.id_ext == external_ref_uuid,
            )
        ).first()
        if checkout_session:
            if payment_data.status == "approved":
                TerminalCheckoutService.mark_payment_approved(
                    db,
                    checkout_session=checkout_session,
                    provider_payment_id=payment_data.provider_payment_id,
                    amount=payment_data.amount,
                )
            elif payment_data.status in ("rejected", "cancelled"):
                TerminalCheckoutService.mark_payment_rejected(
                    db,
                    checkout_session=checkout_session,
                    provider_payment_id=payment_data.provider_payment_id,
                )
            else:
                logger.info("MP webhook status=%s, ignorando checkout session", payment_data.status)
            return {"ok": True}

        pago = db.exec(
            select(Pago).where(
                Pago.id_transaccion_proveedor == external_ref,
            )
        ).first()

        if not pago:
            # external_ref podría ser el session_id_ext, buscar DeviceSession
            device_session = db.exec(
                select(DeviceSession).where(
                    DeviceSession.id_ext == external_ref_uuid,
                )
            ).first()
            if device_session and device_session.pago_id:
                pago = db.get(Pago, device_session.pago_id)

        if not pago:
            logger.warning("MP webhook: pago no encontrado para ref=%s", external_ref)
            return {"ok": True, "ignored": True}

        # Actualizar provider_payment_id si viene
        if payment_data.provider_payment_id:
            pago.id_transaccion_proveedor = payment_data.provider_payment_id

        if payment_data.status == "approved":
            _handle_payment_approved(db, pago, external_ref)
        elif payment_data.status in ("rejected", "cancelled"):
            _handle_payment_rejected(db, pago, external_ref)
        else:
            logger.info("MP webhook status=%s, ignorando", payment_data.status)

        db.commit()

    return {"ok": True}


def _handle_payment_approved(db: Session, pago: Pago, external_ref: str) -> None:
    """Procesa pago aprobado: actualiza estado, completa DeviceSession, calcula puntos"""
    if pago.estado == TipoEstadoPago.APROBADO:
        return  # Ya procesado (idempotencia)

    pago.estado = TipoEstadoPago.APROBADO
    pago.fecha_actualizacion = datetime.utcnow()
    db.add(pago)

    # Buscar DeviceSession asociada
    device_session = db.exec(
        select(DeviceSession).where(
            DeviceSession.pago_id == pago.id,
        )
    ).first()

    if device_session and device_session.status == "pending_payment":
        device_session.status = "completed"
        db.add(device_session)

    # Calcular puntos si hay usuario
    venta = db.exec(
        select(Venta).where(
            Venta.id == pago.id_venta,
            Venta.fecha_hora == pago.fecha_venta,
        )
    ).first()

    if venta and venta.id_usuario:
        already = db.exec(
            select(TransaccionPuntos.id).where(
                TransaccionPuntos.id_venta == int(venta.id),
                TransaccionPuntos.tipo_transaccion == "venta",
            )
        ).first()

        if not already:
            now = datetime.utcnow()
            reglas = db.exec(
                select(ReglaConversionPuntos).where(
                    ReglaConversionPuntos.activo == True,
                    ReglaConversionPuntos.fecha_inicio <= now,
                    (ReglaConversionPuntos.fecha_fin == None)
                    | (ReglaConversionPuntos.fecha_fin >= now),
                )
            ).all()
            calculo = CalculadoraPuntos.calcular_puntos(
                Decimal(str(venta.monto_total)), list(reglas)
            )

            nivel = db.exec(
                select(UsuarioNivel).where(
                    UsuarioNivel.id_usuario == int(venta.id_usuario)
                )
            ).first()
            if not nivel:
                nivel = UsuarioNivel(
                    id_usuario=int(venta.id_usuario), id_nivel=1, puntaje_actual=0
                )
                db.add(nivel)
                db.flush()

            saldo_anterior = int(nivel.puntaje_actual or 0)
            saldo_posterior = max(0, saldo_anterior + int(calculo.puntos_ganados))
            nivel.puntaje_actual = saldo_posterior
            db.add(nivel)

            tx = TransaccionPuntos(
                id_usuario=int(venta.id_usuario),
                puntos_ganados=int(calculo.puntos_ganados),
                puntos_canjeados=0,
                saldo_anterior=max(0, saldo_anterior),
                saldo_posterior=max(0, saldo_posterior),
                id_venta=int(venta.id),
                descripcion=f"Venta {venta.id_ext}",
                tipo_transaccion="venta",
            )
            db.add(tx)

    # Notificar terminal vía bridge
    if device_session:
        _notify_terminal_command(
            device_session, "payment_confirmed", {"status": "approved"}
        )

    # Notificar frontend vía WebSocket
    _try_notify_ws(device_session, "payment_confirmed")


def _handle_payment_rejected(db: Session, pago: Pago, external_ref: str) -> None:
    """Procesa pago rechazado"""
    if pago.estado == TipoEstadoPago.RECHAZADO:
        return

    pago.estado = TipoEstadoPago.RECHAZADO
    pago.fecha_actualizacion = datetime.utcnow()
    db.add(pago)

    device_session = db.exec(
        select(DeviceSession).where(
            DeviceSession.pago_id == pago.id,
        )
    ).first()

    if device_session:
        _notify_terminal_command(
            device_session, "payment_rejected", {"status": "rejected"}
        )
        _try_notify_ws(device_session, "payment_rejected")


def _notify_terminal_command(
    device_session: DeviceSession, command_type: str, payload: dict
) -> None:
    """Envía comando a terminal vía bridge HTTP"""
    from app.models.terminal import TerminalRegistro

    try:
        with Session(engine) as db:
            terminal = db.exec(
                select(TerminalRegistro).where(
                    TerminalRegistro.tenant_id == device_session.tenant_id,
                    TerminalRegistro.equipo_id == device_session.equipo_id,
                    TerminalRegistro.activo == True,
                )
            ).first()

            if not terminal:
                logger.warning("No se encontró terminal para equipo %s", device_session.equipo_id)
                return

            resp = httpx.post(
                f"{settings.mqtt_bridge_base_url}/send-command",
                json={
                    "tenant_id": terminal.tenant_id,
                    "terminal_id_ext": str(terminal.id_ext),
                    "command_type": command_type,
                    "payload": json.dumps(payload, default=str),
                },
                timeout=5,
            )
            if resp.status_code != 200:
                logger.warning("Bridge respondió %s al enviar comando", resp.status_code)
    except Exception as e:
        logger.error("Error notificando terminal: %s", e)


def _try_notify_ws(device_session: DeviceSession, event_type: str) -> None:
    """Intenta notificar al frontend vía WebSocket"""
    if not device_session or not device_session.tenant_id:
        return

    try:
        import asyncio

        from app.routers.ws_telemetria import notify_telemetry

        loop = asyncio.get_running_loop()
        loop.create_task(
            notify_telemetry(
                device_session.tenant_id,
                {
                    "type": event_type,
                    "session_id": str(device_session.id_ext),
                    "equipo_id": device_session.equipo_id,
                    "status": device_session.status,
                },
            )
        )
    except RuntimeError:
        logger.debug("No hay event loop para notificar WS")
