from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Column, Numeric
from sqlmodel import Field

from .base import BaseModel


class DeviceSession(BaseModel, table=True):
    __tablename__ = "device_sessions"

    tenant_id: Optional[int] = Field(foreign_key="tenants.id", default=None, index=True)
    equipo_id: int = Field(foreign_key="equipos.id", index=True)

    uid_hash: Optional[str] = Field(default=None, max_length=128, index=True)
    user_id: Optional[int] = Field(foreign_key="usuarios.id", default=None, index=True)

    status: str = Field(default="created", max_length=20, index=True)

    cerveza_id: int = Field(foreign_key="cervezas.id", index=True)
    price_per_liter: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))

    requested_ml: int = Field(gt=0)
    max_ml: int = Field(gt=0)

    poured_ml: Optional[int] = Field(default=None, ge=0)
    estimated_amount: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))
    final_amount: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    venta_id: Optional[int] = Field(default=None, index=True)
    venta_fecha_hora: Optional[datetime] = Field(default=None, index=True)
    pago_id: Optional[int] = Field(default=None, index=True)

    payment_mode: str = Field(default="wallet", max_length=20, index=True)
    idempotency_key: Optional[str] = Field(default=None, max_length=80, index=True)

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    completed_at: Optional[datetime] = Field(default=None, index=True)
