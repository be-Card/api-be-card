from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel

from .base import BaseModel, TimestampMixin


class Tenant(BaseModel, TimestampMixin, table=True):
    __tablename__ = "tenants"

    nombre: str = Field(max_length=120)
    slug: str = Field(max_length=80, unique=True, index=True)
    activo: bool = Field(default=True, index=True)
    suscripcion_plan: str = Field(default="mensual", max_length=30)
    suscripcion_estado: str = Field(default="activa", max_length=20, index=True)
    suscripcion_hasta: Optional[datetime] = Field(default=None, index=True)
    suscripcion_gracia_hasta: Optional[datetime] = Field(default=None, index=True)
    suscripcion_ultima_cobranza: Optional[datetime] = Field(default=None)
    suscripcion_precio_centavos: int = Field(default=0)
    suscripcion_moneda: str = Field(default="ARS", max_length=10)
    suscripcion_periodo_dias: int = Field(default=30)


class TenantUser(SQLModel, table=True):
    __tablename__ = "tenant_users"

    tenant_id: int = Field(foreign_key="tenants.id", primary_key=True)
    user_id: int = Field(foreign_key="usuarios.id", primary_key=True)
    rol: str = Field(max_length=30, default="member")
    creado_el: datetime = Field(default_factory=datetime.utcnow)


class TenantPayment(BaseModel, TimestampMixin, table=True):
    __tablename__ = "tenant_payments"

    tenant_id: int = Field(foreign_key="tenants.id", index=True)
    amount_centavos: int = Field(default=0)
    currency: str = Field(default="ARS", max_length=10)
    status: str = Field(default="paid", max_length=20, index=True)
    paid_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    payment_method: Optional[str] = Field(default=None, max_length=30)
    notes: Optional[str] = Field(default=None, max_length=500)
    failure_reason: Optional[str] = Field(default=None, max_length=200)
    refunded_at: Optional[datetime] = Field(default=None)
    period_start: Optional[datetime] = Field(default=None, index=True)
    period_end: Optional[datetime] = Field(default=None, index=True)
    provider: Optional[str] = Field(default=None, max_length=30)
    provider_payment_id: Optional[str] = Field(default=None, max_length=120, index=True)
