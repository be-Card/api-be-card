"""
Abstracción de pasarela de pago.
Interfaz base + factory + schemas de datos comunes.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Optional


@dataclass
class QRPaymentResult:
    """Resultado de crear una intención de pago QR"""
    qr_data: str
    provider_payment_id: str
    external_reference: str


@dataclass
class WebhookPaymentData:
    """Datos extraídos de una notificación webhook"""
    provider_payment_id: str
    external_reference: str
    status: str  # "approved", "rejected", "pending", "cancelled"
    amount: Optional[Decimal] = None


@dataclass
class PaymentStatusResult:
    """Resultado de consultar estado de un pago"""
    status: str
    provider_payment_id: str
    amount: Optional[Decimal] = None


class PaymentGatewayBase(ABC):
    """Interfaz abstracta para pasarelas de pago"""

    @abstractmethod
    def create_qr_payment(
        self,
        *,
        amount: Decimal,
        description: str,
        external_reference: str,
        notification_url: Optional[str] = None,
    ) -> QRPaymentResult:
        ...

    @abstractmethod
    def verify_webhook_signature(
        self,
        headers: Dict[str, str],
        body: bytes,
    ) -> bool:
        ...

    @abstractmethod
    def parse_webhook(
        self,
        headers: Dict[str, str],
        body: bytes,
    ) -> WebhookPaymentData:
        ...

    @abstractmethod
    def get_payment_status(
        self,
        provider_payment_id: str,
    ) -> PaymentStatusResult:
        ...


def get_payment_gateway(gateway_name: Optional[str] = None) -> PaymentGatewayBase:
    """Factory: retorna instancia de la pasarela según nombre."""
    from app.core.config import settings

    name = gateway_name or settings.payment_gateway

    if name == "mercadopago":
        from app.services.mercadopago_gateway import MercadoPagoGateway
        return MercadoPagoGateway()

    raise ValueError(f"Gateway no soportado: {name}")
