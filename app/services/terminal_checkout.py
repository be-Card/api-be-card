from __future__ import annotations

import json
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from typing import Optional
from uuid import UUID

import httpx
from sqlmodel import Session, select

from app.core.config import settings
from app.models.beer import Cerveza
from app.models.pricing import ConsultaPrecio
from app.models.sales_point import Equipo, PuntoVenta
from app.models.terminal import TerminalRegistro
from app.models.terminal_checkout import TerminalCheckoutSession
from app.services.payment_gateway import get_payment_gateway
from app.services.pricing import PricingService
from app.services.terminales import TerminalService


class TerminalCheckoutService:
    @staticmethod
    def create_screen_session(
        session: Session,
        *,
        tenant_id: int,
        terminal_id_ext: UUID,
        checkout_base_url: str,
    ) -> TerminalCheckoutSession:
        terminal = TerminalService.get_terminal_by_id_ext(
            session,
            tenant_id=tenant_id,
            terminal_id_ext=terminal_id_ext,
        )
        if terminal is None:
            raise ValueError("TERMINAL_NOT_FOUND")

        equipo = session.exec(
            select(Equipo)
            .join(PuntoVenta, Equipo.id_punto_de_venta == PuntoVenta.id)
            .where(
                Equipo.id == terminal.equipo_id,
                Equipo.activo == True,
                PuntoVenta.tenant_id == tenant_id,
                PuntoVenta.activo == True,
            )
        ).first()
        if equipo is None or equipo.id_cerveza is None:
            raise ValueError("TERMINAL_WITHOUT_BEER")

        cerveza = session.get(Cerveza, equipo.id_cerveza)
        if cerveza is None:
            raise ValueError("BEER_NOT_FOUND")

        consulta = ConsultaPrecio(
            id_cerveza=equipo.id_cerveza,
            id_equipo=equipo.id,
            id_punto_venta=equipo.id_punto_de_venta,
            fecha_consulta=datetime.utcnow(),
            cantidad=1,
        )
        calculo = PricingService.calcular_precio(session, consulta, tenant_id=tenant_id)
        price_per_liter = Decimal(str(calculo.precio_final)).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        now = datetime.utcnow()
        open_sessions = session.exec(
            select(TerminalCheckoutSession).where(
                TerminalCheckoutSession.terminal_id == terminal.id,
                TerminalCheckoutSession.status.in_(
                    ("pending_selection", "pending_payment")
                ),
            )
        ).all()
        for existing in open_sessions:
            existing.status = "expired"
            existing.updated_at = now
            session.add(existing)

        checkout_session = TerminalCheckoutSession(
            tenant_id=tenant_id,
            terminal_id=terminal.id,
            equipo_id=equipo.id,
            cerveza_id=cerveza.id,
            terminal_nombre=terminal.nombre,
            cerveza_nombre=cerveza.nombre,
            cerveza_tipo=cerveza.tipo,
            price_per_liter=price_per_liter,
            checkout_url="pending",
            expires_at=now + timedelta(minutes=15),
        )
        session.add(checkout_session)
        session.flush()

        checkout_session.checkout_url = f"{checkout_base_url.rstrip('/')}/{checkout_session.id_ext}"
        checkout_session.updated_at = now
        session.add(checkout_session)
        session.commit()
        session.refresh(checkout_session)

        TerminalCheckoutService.push_checkout_to_screen(
            session,
            checkout_session=checkout_session,
        )
        return checkout_session

    @staticmethod
    def get_by_id_ext(
        session: Session,
        *,
        session_id_ext: str,
    ) -> Optional[TerminalCheckoutSession]:
        try:
            session_uuid = UUID(str(session_id_ext))
        except ValueError:
            return None
        return session.exec(
            select(TerminalCheckoutSession).where(
                TerminalCheckoutSession.id_ext == session_uuid
            )
        ).first()

    @staticmethod
    def create_payment(
        session: Session,
        *,
        checkout_session: TerminalCheckoutSession,
        requested_ml: Optional[int],
        amount: Optional[Decimal],
        notification_base_url: Optional[str],
    ) -> TerminalCheckoutSession:
        if checkout_session.status == "approved":
            raise ValueError("SESSION_ALREADY_APPROVED")
        if checkout_session.status == "expired" or checkout_session.expires_at < datetime.utcnow():
            raise ValueError("SESSION_EXPIRED")

        selected_ml, selected_amount = TerminalCheckoutService._normalize_selection(
            price_per_liter=Decimal(str(checkout_session.price_per_liter)),
            requested_ml=requested_ml,
            amount=amount,
        )

        gateway = get_payment_gateway()
        notification_url = None
        if notification_base_url:
            notification_url = (
                f"{notification_base_url.rstrip('/')}/api/v1/webhooks/mercadopago"
            )

        result = gateway.create_qr_payment(
            amount=selected_amount,
            description=f"{checkout_session.cerveza_nombre} - {selected_ml} ml",
            external_reference=str(checkout_session.id_ext),
            notification_url=notification_url,
        )

        checkout_session.requested_ml = selected_ml
        checkout_session.requested_amount = selected_amount
        checkout_session.provider_payment_id = result.provider_payment_id or checkout_session.provider_payment_id
        checkout_session.mercadopago_qr_data = result.qr_data
        checkout_session.status = "pending_payment"
        checkout_session.updated_at = datetime.utcnow()
        session.add(checkout_session)
        session.commit()
        session.refresh(checkout_session)
        return checkout_session

    @staticmethod
    def mark_payment_approved(
        session: Session,
        *,
        checkout_session: TerminalCheckoutSession,
        provider_payment_id: Optional[str],
        amount: Optional[Decimal],
    ) -> TerminalCheckoutSession:
        if checkout_session.status == "approved":
            return checkout_session

        checkout_session.status = "approved"
        checkout_session.provider_payment_id = provider_payment_id or checkout_session.provider_payment_id
        if amount is not None:
            checkout_session.requested_amount = Decimal(str(amount)).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
        checkout_session.approved_at = datetime.utcnow()
        checkout_session.updated_at = datetime.utcnow()
        session.add(checkout_session)
        session.commit()
        session.refresh(checkout_session)

        TerminalCheckoutService._send_terminal_command(
            session,
            terminal_id=checkout_session.terminal_id,
            command_type="payment_confirmed",
            payload={
                "session_id": str(checkout_session.id_ext),
                "equipo_id": checkout_session.equipo_id,
                "cerveza_id": checkout_session.cerveza_id,
                "requested_ml": checkout_session.requested_ml,
                "requested_amount": str(checkout_session.requested_amount),
                "provider_payment_id": checkout_session.provider_payment_id,
                "status": "approved",
            },
        )
        return checkout_session

    @staticmethod
    def mark_payment_rejected(
        session: Session,
        *,
        checkout_session: TerminalCheckoutSession,
        provider_payment_id: Optional[str],
    ) -> TerminalCheckoutSession:
        if checkout_session.status == "rejected":
            return checkout_session

        checkout_session.status = "rejected"
        checkout_session.provider_payment_id = provider_payment_id or checkout_session.provider_payment_id
        checkout_session.updated_at = datetime.utcnow()
        session.add(checkout_session)
        session.commit()
        session.refresh(checkout_session)

        TerminalCheckoutService._send_terminal_command(
            session,
            terminal_id=checkout_session.terminal_id,
            command_type="payment_rejected",
            payload={
                "session_id": str(checkout_session.id_ext),
                "status": checkout_session.status,
            },
        )
        return checkout_session

    @staticmethod
    def push_checkout_to_screen(
        session: Session,
        *,
        checkout_session: TerminalCheckoutSession,
    ) -> None:
        TerminalCheckoutService._send_terminal_command(
            session,
            terminal_id=checkout_session.terminal_id,
            command_type="render_checkout_qr",
            payload={
                "session_id": str(checkout_session.id_ext),
                "qr_data": checkout_session.checkout_url,
                "qr_kind": "checkout_url",
                "cerveza_nombre": checkout_session.cerveza_nombre,
                "cerveza_tipo": checkout_session.cerveza_tipo,
                "terminal_nombre": checkout_session.terminal_nombre,
                "price_per_liter": str(checkout_session.price_per_liter),
                "expires_at": checkout_session.expires_at.isoformat(),
            },
        )

    @staticmethod
    def _normalize_selection(
        *,
        price_per_liter: Decimal,
        requested_ml: Optional[int],
        amount: Optional[Decimal],
    ) -> tuple[int, Decimal]:
        if requested_ml is None and amount is None:
            raise ValueError("AMOUNT_OR_VOLUME_REQUIRED")

        if requested_ml is not None:
            selected_ml = int(requested_ml)
            selected_amount = (
                (Decimal(selected_ml) / Decimal(1000)) * price_per_liter
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            return selected_ml, selected_amount

        selected_amount = Decimal(str(amount)).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
        if selected_amount <= 0:
            raise ValueError("INVALID_AMOUNT")

        selected_ml = int(
            ((selected_amount / price_per_liter) * Decimal(1000)).to_integral_value(
                rounding=ROUND_DOWN
            )
        )
        if selected_ml <= 0:
            raise ValueError("INVALID_AMOUNT")
        return selected_ml, selected_amount

    @staticmethod
    def _send_terminal_command(
        session: Session,
        *,
        terminal_id: int,
        command_type: str,
        payload: dict,
    ) -> None:
        terminal = session.get(TerminalRegistro, terminal_id)
        if terminal is None or not terminal.activo:
            return

        response = httpx.post(
            f"{settings.mqtt_bridge_base_url}/send-command",
            json={
                "tenant_id": terminal.tenant_id,
                "terminal_id_ext": str(terminal.id_ext),
                "command_type": command_type,
                "payload": json.dumps(payload, default=str),
            },
            timeout=5,
        )
        response.raise_for_status()

        session_id = payload.get("session_id")
        if not session_id:
            return

        try:
            session_uuid = UUID(str(session_id))
        except ValueError:
            return

        checkout_session = session.exec(
            select(TerminalCheckoutSession).where(
                TerminalCheckoutSession.terminal_id == terminal_id,
                TerminalCheckoutSession.id_ext == session_uuid,
            )
        ).first()
        if checkout_session is not None:
            checkout_session.command_sent_at = datetime.utcnow()
            checkout_session.updated_at = datetime.utcnow()
            session.add(checkout_session)
            session.commit()
