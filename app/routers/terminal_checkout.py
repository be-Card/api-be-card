from __future__ import annotations

from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session

from app.core.config import settings
from app.core.database import get_session
from app.core.tenant import get_current_tenant
from app.models.tenant import Tenant
from app.models.terminal_checkout import (
    TerminalCheckoutCreateResponse,
    TerminalCheckoutPaymentRequest,
    TerminalCheckoutPaymentResponse,
    TerminalCheckoutPublicRead,
    TerminalCheckoutSessionRead,
)
from app.models.user_extended import Usuario
from app.routers.auth import get_current_user
from app.services.terminal_checkout import TerminalCheckoutService


router = APIRouter(prefix="/terminal-checkout", tags=["terminal-checkout"])


@router.post(
    "/terminales/{terminal_id_ext}/sessions",
    response_model=TerminalCheckoutCreateResponse,
    status_code=201,
)
def create_terminal_checkout_session(
    terminal_id_ext: UUID,
    request: Request,
    session: Session = Depends(get_session),
    tenant: Tenant = Depends(get_current_tenant),
    current_user: Usuario = Depends(get_current_user),
):
    del current_user
    checkout_base_url = _resolve_checkout_frontend_base_url(request)
    try:
        checkout_session = TerminalCheckoutService.create_screen_session(
            session,
            tenant_id=tenant.id,
            terminal_id_ext=terminal_id_ext,
            checkout_base_url=f"{checkout_base_url}/checkout",
        )
    except ValueError as exc:
        detail = {
            "TERMINAL_NOT_FOUND": "Terminal no encontrada",
            "TERMINAL_WITHOUT_BEER": "La terminal no tiene una birra asociada",
            "BEER_NOT_FOUND": "La birra configurada no existe",
        }.get(str(exc), "No se pudo crear la sesión de cobro")
        raise HTTPException(status_code=400, detail=detail) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="No se pudo inicializar el QR") from exc

    return TerminalCheckoutCreateResponse(
        session_id=str(checkout_session.id_ext),
        status=checkout_session.status,
        checkout_url=checkout_session.checkout_url,
        terminal_nombre=checkout_session.terminal_nombre,
        cerveza_nombre=checkout_session.cerveza_nombre,
        cerveza_tipo=checkout_session.cerveza_tipo,
        price_per_liter=checkout_session.price_per_liter,
        expires_at=checkout_session.expires_at,
    )


@router.get("/sessions/{session_id}", response_model=TerminalCheckoutSessionRead)
def get_terminal_checkout_session(
    session_id: str,
    session: Session = Depends(get_session),
    tenant: Tenant = Depends(get_current_tenant),
    current_user: Usuario = Depends(get_current_user),
):
    del current_user
    checkout_session = TerminalCheckoutService.get_by_id_ext(
        session,
        session_id_ext=session_id,
    )
    if checkout_session is None or checkout_session.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")

    return TerminalCheckoutSessionRead(
        id=checkout_session.id,
        id_ext=str(checkout_session.id_ext),
        tenant_id=checkout_session.tenant_id,
        terminal_id=checkout_session.terminal_id,
        equipo_id=checkout_session.equipo_id,
        cerveza_id=checkout_session.cerveza_id,
        status=checkout_session.status,
        payment_provider=checkout_session.payment_provider,
        terminal_nombre=checkout_session.terminal_nombre,
        cerveza_nombre=checkout_session.cerveza_nombre,
        cerveza_tipo=checkout_session.cerveza_tipo,
        price_per_liter=checkout_session.price_per_liter,
        requested_ml=checkout_session.requested_ml,
        requested_amount=checkout_session.requested_amount,
        checkout_url=checkout_session.checkout_url,
        mercadopago_qr_data=checkout_session.mercadopago_qr_data,
        provider_payment_id=checkout_session.provider_payment_id,
        expires_at=checkout_session.expires_at,
        approved_at=checkout_session.approved_at,
        command_sent_at=checkout_session.command_sent_at,
        created_at=checkout_session.created_at,
        updated_at=checkout_session.updated_at,
    )


@router.get("/public/{session_id}", include_in_schema=False)
def public_terminal_checkout_page(
    session_id: str,
    session: Session = Depends(get_session),
):
    checkout_session = TerminalCheckoutService.get_by_id_ext(
        session,
        session_id_ext=session_id,
    )
    if checkout_session is None:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")

    frontend_base_url = _resolve_checkout_frontend_base_url()
    return RedirectResponse(
        url=f"{frontend_base_url}/checkout/{session_id}",
        status_code=307,
    )


@router.get("/public/{session_id}/data", response_model=TerminalCheckoutPublicRead)
def get_public_terminal_checkout_data(
    session_id: str,
    session: Session = Depends(get_session),
):
    checkout_session = TerminalCheckoutService.get_by_id_ext(
        session,
        session_id_ext=session_id,
    )
    if checkout_session is None:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")

    return TerminalCheckoutPublicRead(
        session_id=str(checkout_session.id_ext),
        status=checkout_session.status,
        terminal_nombre=checkout_session.terminal_nombre,
        cerveza_nombre=checkout_session.cerveza_nombre,
        cerveza_tipo=checkout_session.cerveza_tipo,
        price_per_liter=checkout_session.price_per_liter,
        requested_ml=checkout_session.requested_ml,
        requested_amount=checkout_session.requested_amount,
        expires_at=checkout_session.expires_at,
    )


@router.post(
    "/public/{session_id}/payments",
    response_model=TerminalCheckoutPaymentResponse,
)
def create_public_terminal_checkout_payment(
    session_id: str,
    payload: TerminalCheckoutPaymentRequest,
    request: Request,
    session: Session = Depends(get_session),
):
    checkout_session = TerminalCheckoutService.get_by_id_ext(
        session,
        session_id_ext=session_id,
    )
    if checkout_session is None:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")

    try:
        updated_session = TerminalCheckoutService.create_payment(
            session,
            checkout_session=checkout_session,
            requested_ml=payload.requested_ml,
            amount=payload.amount,
            notification_base_url=_resolve_notification_base_url(request),
        )
    except ValueError as exc:
        detail = {
            "AMOUNT_OR_VOLUME_REQUIRED": "Tenés que indicar mililitros o monto",
            "INVALID_AMOUNT": "El monto seleccionado no es válido para esta terminal",
            "SESSION_EXPIRED": "La sesión de cobro venció",
            "SESSION_ALREADY_APPROVED": "Esta sesión ya fue aprobada",
        }.get(str(exc), "No se pudo crear el pago")
        raise HTTPException(status_code=400, detail=detail) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Error al crear el pago") from exc

    qr_data = updated_session.mercadopago_qr_data or ""
    payment_flow = "redirect" if qr_data.startswith("http://") or qr_data.startswith("https://") else "terminal_qr"
    return TerminalCheckoutPaymentResponse(
        session_id=str(updated_session.id_ext),
        status=updated_session.status,
        requested_ml=int(updated_session.requested_ml or 0),
        requested_amount=Decimal(str(updated_session.requested_amount or 0)).quantize(Decimal("0.01")),
        qr_data=qr_data,
        payment_flow=payment_flow,
        provider_payment_id=updated_session.provider_payment_id,
    )


def _resolve_checkout_frontend_base_url(request: Optional[Request] = None) -> str:
    if settings.frontend_url:
        return settings.frontend_url.rstrip("/")
    if settings.backend_public_url:
        return settings.backend_public_url.rstrip("/")
    if request is None:
        raise HTTPException(status_code=500, detail="No hay URL pública configurada para el checkout")
    return str(request.base_url).rstrip("/")


def _resolve_notification_base_url(request: Request) -> Optional[str]:
    if settings.backend_public_url:
        return settings.backend_public_url.rstrip("/")
    return str(request.base_url).rstrip("/")
