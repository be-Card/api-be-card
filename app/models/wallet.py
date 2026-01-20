from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Column, Numeric
from sqlmodel import Field

from .base import BaseModel


class Wallet(BaseModel, table=True):
    __tablename__ = "wallets"

    tenant_id: Optional[int] = Field(foreign_key="tenants.id", default=None, index=True)
    owner_type: str = Field(max_length=20, index=True)
    owner_user_id: Optional[int] = Field(foreign_key="usuarios.id", default=None, index=True)
    owner_card_id: Optional[int] = Field(foreign_key="cards.id", default=None, index=True)
    balance: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(12, 2), nullable=False))
    activo: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class WalletTxn(BaseModel, table=True):
    __tablename__ = "wallet_txns"

    wallet_id: int = Field(foreign_key="wallets.id", index=True)
    direction: str = Field(max_length=10, index=True)
    amount: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    balance_before: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    balance_after: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    reference_type: Optional[str] = Field(default=None, max_length=30, index=True)
    reference_id: Optional[str] = Field(default=None, max_length=80, index=True)
    idempotency_key: Optional[str] = Field(default=None, max_length=80, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    created_by: Optional[int] = Field(foreign_key="usuarios.id", default=None, index=True)

