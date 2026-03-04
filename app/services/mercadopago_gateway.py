"""
Implementación de PaymentGatewayBase para MercadoPago.
Usa la API de MercadoPago (QR dinámico / Point Integration).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from decimal import Decimal
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings
from app.services.payment_gateway import (
    PaymentGatewayBase,
    PaymentStatusResult,
    QRPaymentResult,
    WebhookPaymentData,
)

logger = logging.getLogger(__name__)

MP_API_BASE = "https://api.mercadopago.com"


class MercadoPagoGateway(PaymentGatewayBase):

    def __init__(self) -> None:
        if not settings.mp_access_token:
            raise ValueError("MP_ACCESS_TOKEN no configurado")
        self._token = settings.mp_access_token

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    # ── create_qr_payment ────────────────────────────────────────────────

    def create_qr_payment(
        self,
        *,
        amount: Decimal,
        description: str,
        external_reference: str,
        notification_url: Optional[str] = None,
    ) -> QRPaymentResult:
        """
        Crea una intención de pago QR dinámico.
        Si mp_user_id y mp_pos_id están configurados, usa QR Point Integration
        (in-store). Sino, usa preference con QR genérico.
        """
        if settings.mp_user_id and settings.mp_pos_id:
            return self._create_qr_point(
                amount=amount,
                description=description,
                external_reference=external_reference,
                notification_url=notification_url,
            )
        return self._create_qr_preference(
            amount=amount,
            description=description,
            external_reference=external_reference,
            notification_url=notification_url,
        )

    def _create_qr_point(
        self, *, amount: Decimal, description: str,
        external_reference: str, notification_url: Optional[str],
    ) -> QRPaymentResult:
        """QR Point Integration (in-store POS)"""
        url = (
            f"{MP_API_BASE}/instore/orders/qr/seller/collectors"
            f"/{settings.mp_user_id}/pos/{settings.mp_pos_id}/qrs"
        )
        body: Dict[str, Any] = {
            "external_reference": external_reference,
            "title": description,
            "total_amount": float(amount),
            "items": [
                {
                    "title": description,
                    "unit_price": float(amount),
                    "quantity": 1,
                    "unit_measure": "unit",
                    "total_amount": float(amount),
                }
            ],
        }
        if notification_url:
            body["notification_url"] = notification_url

        with httpx.Client(timeout=15) as client:
            resp = client.put(url, json=body, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()

        qr_data = data.get("qr_data", "")
        return QRPaymentResult(
            qr_data=qr_data,
            provider_payment_id="",  # se obtiene vía webhook
            external_reference=external_reference,
        )

    def _create_qr_preference(
        self, *, amount: Decimal, description: str,
        external_reference: str, notification_url: Optional[str],
    ) -> QRPaymentResult:
        """QR vía Checkout Pro preference (fallback genérico)"""
        url = f"{MP_API_BASE}/checkout/preferences"
        body: Dict[str, Any] = {
            "external_reference": external_reference,
            "items": [
                {
                    "title": description,
                    "unit_price": float(amount),
                    "quantity": 1,
                    "currency_id": "ARS",
                }
            ],
        }
        if notification_url:
            body["notification_url"] = notification_url

        with httpx.Client(timeout=15) as client:
            resp = client.post(url, json=body, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()

        init_point = data.get("init_point", "")
        return QRPaymentResult(
            qr_data=init_point,
            provider_payment_id=str(data.get("id", "")),
            external_reference=external_reference,
        )

    # ── verify_webhook_signature ─────────────────────────────────────────

    def verify_webhook_signature(
        self,
        headers: Dict[str, str],
        body: bytes,
    ) -> bool:
        """
        Valida la firma del webhook de MercadoPago.
        MP envía X-Signature con ts=... y v1=...
        Si no hay webhook_secret configurado, skip validation (dev mode).
        """
        secret = settings.mp_webhook_secret
        if not secret:
            logger.warning("MP webhook secret not configured, skipping signature validation")
            return True

        x_signature = headers.get("x-signature", "")
        x_request_id = headers.get("x-request-id", "")

        if not x_signature:
            return False

        parts = {}
        for part in x_signature.split(","):
            kv = part.strip().split("=", 1)
            if len(kv) == 2:
                parts[kv[0]] = kv[1]

        ts = parts.get("ts", "")
        v1 = parts.get("v1", "")

        if not ts or not v1:
            return False

        # Parsear body para obtener data.id
        try:
            payload = json.loads(body)
            data_id = str(payload.get("data", {}).get("id", ""))
        except (json.JSONDecodeError, AttributeError):
            return False

        manifest = f"id:{data_id};request-id:{x_request_id};ts:{ts};"
        expected = hmac.new(
            secret.encode("utf-8"),
            manifest.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, v1)

    # ── parse_webhook ────────────────────────────────────────────────────

    def parse_webhook(
        self,
        headers: Dict[str, str],
        body: bytes,
    ) -> WebhookPaymentData:
        """
        Parsea notificación de MP. Puede ser IPN o webhook v2.
        Para IPN topic=payment: consulta el pago por ID.
        Para webhook v2 action=payment.updated: idem.
        """
        payload = json.loads(body)
        action = payload.get("action", "")
        topic = payload.get("topic", "")

        # Webhook v2
        if action in ("payment.created", "payment.updated"):
            payment_id = str(payload.get("data", {}).get("id", ""))
            return self._fetch_payment_data(payment_id)

        # IPN clásico
        if topic == "payment":
            payment_id = str(payload.get("data", {}).get("id", payload.get("id", "")))
            return self._fetch_payment_data(payment_id)

        # Merchant order (QR Point)
        if topic == "merchant_order" or action == "point_integration_wh":
            resource = payload.get("resource", "")
            if resource:
                return self._fetch_merchant_order(resource)
            order_id = str(payload.get("data", {}).get("id", ""))
            return self._fetch_merchant_order(
                f"{MP_API_BASE}/merchant_orders/{order_id}"
            )

        raise ValueError(f"Tipo de webhook no soportado: action={action}, topic={topic}")

    def _fetch_payment_data(self, payment_id: str) -> WebhookPaymentData:
        """Consulta un pago en MP por su ID"""
        url = f"{MP_API_BASE}/v1/payments/{payment_id}"
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()

        status_map = {
            "approved": "approved",
            "authorized": "approved",
            "rejected": "rejected",
            "cancelled": "cancelled",
            "refunded": "cancelled",
            "charged_back": "cancelled",
            "in_process": "pending",
            "pending": "pending",
        }

        return WebhookPaymentData(
            provider_payment_id=str(data.get("id", "")),
            external_reference=data.get("external_reference", ""),
            status=status_map.get(data.get("status", ""), "pending"),
            amount=Decimal(str(data.get("transaction_amount", 0))),
        )

    def _fetch_merchant_order(self, resource_url: str) -> WebhookPaymentData:
        """Consulta merchant_order y extrae el pago"""
        with httpx.Client(timeout=10) as client:
            resp = client.get(resource_url, headers=self._headers())
            resp.raise_for_status()
            order = resp.json()

        external_reference = order.get("external_reference", "")
        payments = order.get("payments", [])

        for p in payments:
            if p.get("status") == "approved":
                return WebhookPaymentData(
                    provider_payment_id=str(p.get("id", "")),
                    external_reference=external_reference,
                    status="approved",
                    amount=Decimal(str(p.get("transaction_amount", 0))),
                )

        # Sin pago aprobado, retornar el estado del último pago
        if payments:
            last = payments[-1]
            return WebhookPaymentData(
                provider_payment_id=str(last.get("id", "")),
                external_reference=external_reference,
                status=last.get("status", "pending"),
                amount=Decimal(str(last.get("transaction_amount", 0))),
            )

        return WebhookPaymentData(
            provider_payment_id="",
            external_reference=external_reference,
            status="pending",
        )

    # ── get_payment_status ───────────────────────────────────────────────

    def get_payment_status(
        self,
        provider_payment_id: str,
    ) -> PaymentStatusResult:
        data = self._fetch_payment_data(provider_payment_id)
        return PaymentStatusResult(
            status=data.status,
            provider_payment_id=data.provider_payment_id,
            amount=data.amount,
        )
