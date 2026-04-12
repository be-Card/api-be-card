from __future__ import annotations

from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
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
    checkout_base_url = _resolve_public_base_url(request)
    try:
        checkout_session = TerminalCheckoutService.create_screen_session(
            session,
            tenant_id=tenant.id,
            terminal_id_ext=terminal_id_ext,
            checkout_base_url=f"{checkout_base_url}/api/v1/terminal-checkout/public",
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


@router.get("/public/{session_id}", response_class=HTMLResponse, include_in_schema=False)
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

    return HTMLResponse(
        content=f"""
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>BeCard x Mercado Pago</title>
  <style>
    body {{ font-family: Arial, sans-serif; max-width: 560px; margin: 0 auto; padding: 24px; background: #111827; color: #f9fafb; }}
    .card {{ background: #1f2937; border-radius: 16px; padding: 24px; }}
    .field {{ margin-bottom: 16px; }}
    label {{ display: block; margin-bottom: 8px; font-weight: 700; }}
    input, button {{ width: 100%; padding: 14px; border-radius: 12px; border: 0; box-sizing: border-box; }}
    input {{ background: #f9fafb; color: #111827; }}
    button {{ background: #00a650; color: white; font-size: 16px; font-weight: 700; cursor: pointer; }}
    .secondary {{ margin-top: 12px; background: #374151; }}
    .muted {{ color: #9ca3af; font-size: 14px; }}
    #message {{ margin-top: 16px; white-space: pre-wrap; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>{checkout_session.cerveza_nombre}</h1>
    <p>{checkout_session.cerveza_tipo or ""}</p>
    <p class="muted">Terminal: {checkout_session.terminal_nombre}</p>
    <p class="muted">Precio por litro: ${checkout_session.price_per_liter}</p>
    <div class="field">
      <label for="requested_ml">Mililitros</label>
      <input id="requested_ml" type="number" min="100" step="50" placeholder="Ej: 500" />
    </div>
    <div class="field">
      <label for="amount">O monto en pesos</label>
      <input id="amount" type="number" min="1" step="0.01" placeholder="Ej: 2500" />
    </div>
    <button id="pay">Continuar con Mercado Pago</button>
    <button id="refresh" class="secondary" type="button">Ver estado</button>
    <div id="message"></div>
  </div>
  <script>
    const message = document.getElementById("message");
    async function createPayment() {{
      message.textContent = "Generando pago...";
      const requestedMl = document.getElementById("requested_ml").value;
      const amount = document.getElementById("amount").value;
      const body = {{}};
      if (requestedMl) body.requested_ml = Number(requestedMl);
      if (amount) body.amount = amount;
      const response = await fetch("/api/v1/terminal-checkout/public/{session_id}/payments", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify(body),
      }});
      const data = await response.json();
      if (!response.ok) {{
        message.textContent = data.detail || "No se pudo generar el pago";
        return;
      }}
      if (data.payment_flow === "redirect" && data.qr_data.startsWith("http")) {{
        window.location.href = data.qr_data;
        return;
      }}
      message.textContent = "El QR de Mercado Pago ya se envió a la pantalla de la terminal. Escanealo para completar el pago.";
    }}
    async function refreshState() {{
      const response = await fetch("/api/v1/terminal-checkout/public/{session_id}/data");
      const data = await response.json();
      if (!response.ok) {{
        message.textContent = data.detail || "No se pudo consultar el estado";
        return;
      }}
      if (data.status === "approved") {{
        message.textContent = "Pago aprobado. La terminal ya recibió la autorización para despachar.";
        return;
      }}
      if (data.status === "rejected") {{
        message.textContent = "El pago fue rechazado.";
        return;
      }}
      message.textContent = "Estado actual: " + data.status;
    }}
    document.getElementById("pay").addEventListener("click", createPayment);
    document.getElementById("refresh").addEventListener("click", refreshState);
  </script>
</body>
</html>
""".strip()
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


def _resolve_public_base_url(request: Request) -> str:
    if settings.backend_public_url:
        return settings.backend_public_url.rstrip("/")
    return str(request.base_url).rstrip("/")


def _resolve_notification_base_url(request: Request) -> Optional[str]:
    if settings.backend_public_url:
        return settings.backend_public_url.rstrip("/")
    return str(request.base_url).rstrip("/")
