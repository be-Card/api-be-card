from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field

from .base import BaseModel


class Card(BaseModel, table=True):
    __tablename__ = "cards"

    tenant_id: Optional[int] = Field(foreign_key="tenants.id", default=None, index=True)
    uid_hash: str = Field(max_length=128, unique=True, index=True)
    activo: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class CardAssignment(BaseModel, table=True):
    __tablename__ = "card_assignments"

    tenant_id: Optional[int] = Field(foreign_key="tenants.id", default=None, index=True)
    card_id: int = Field(foreign_key="cards.id", index=True)
    user_id: Optional[int] = Field(foreign_key="usuarios.id", default=None, index=True)
    assignment_type: str = Field(max_length=30, index=True)
    activo: bool = Field(default=True, index=True)
    assigned_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    assigned_by: Optional[int] = Field(foreign_key="usuarios.id", default=None, index=True)
    unassigned_at: Optional[datetime] = Field(default=None, index=True)

