from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Column, Numeric
from sqlmodel import Field, SQLModel

from .base import BaseModel


class TerminalCheckoutSession(BaseModel, table=True):
    __tablename__ = "terminal_checkout_sessions"

    tenant_id: int = Field(foreign_key="tenants.id", index=True)
    terminal_id: int = Field(foreign_key="terminales_registro.id", index=True)
    equipo_id: int = Field(foreign_key="equipos.id", index=True)
    cerveza_id: int = Field(foreign_key="cervezas.id", index=True)

    status: str = Field(default="pending_selection", max_length=30, index=True)
    payment_provider: str = Field(default="mercadopago", max_length=40)

    terminal_nombre: str = Field(max_length=100)
    cerveza_nombre: str = Field(max_length=80)
    cerveza_tipo: Optional[str] = Field(default=None, max_length=50)

    price_per_liter: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))
    requested_ml: Optional[int] = Field(default=None, ge=1)
    requested_amount: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))

    checkout_url: str = Field(max_length=500)
    mercadopago_qr_data: Optional[str] = Field(default=None)
    provider_payment_id: Optional[str] = Field(default=None, max_length=120, index=True)

    expires_at: datetime = Field(index=True)
    approved_at: Optional[datetime] = Field(default=None, index=True)
    command_sent_at: Optional[datetime] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class TerminalCheckoutSessionRead(SQLModel):
    id: int
    id_ext: str
    tenant_id: int
    terminal_id: int
    equipo_id: int
    cerveza_id: int
    status: str
    payment_provider: str
    terminal_nombre: str
    cerveza_nombre: str
    cerveza_tipo: Optional[str]
    price_per_liter: Decimal
    requested_ml: Optional[int]
    requested_amount: Optional[Decimal]
    checkout_url: str
    mercadopago_qr_data: Optional[str]
    provider_payment_id: Optional[str]
    expires_at: datetime
    approved_at: Optional[datetime]
    command_sent_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class TerminalCheckoutPublicRead(SQLModel):
    session_id: str
    status: str
    terminal_nombre: str
    cerveza_nombre: str
    cerveza_tipo: Optional[str]
    price_per_liter: Decimal
    requested_ml: Optional[int] = None
    requested_amount: Optional[Decimal] = None
    expires_at: datetime


class TerminalCheckoutCreateResponse(SQLModel):
    session_id: str
    status: str
    checkout_url: str
    terminal_nombre: str
    cerveza_nombre: str
    cerveza_tipo: Optional[str]
    price_per_liter: Decimal
    expires_at: datetime


class TerminalCheckoutPaymentRequest(SQLModel):
    requested_ml: Optional[int] = Field(default=None, ge=1)
    amount: Optional[Decimal] = Field(default=None, gt=Decimal("0.00"))


class TerminalCheckoutPaymentResponse(SQLModel):
    session_id: str
    status: str
    requested_ml: int
    requested_amount: Decimal
    qr_data: str
    payment_flow: str
    provider_payment_id: Optional[str] = None
