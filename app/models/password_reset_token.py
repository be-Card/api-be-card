from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field


class PasswordResetToken(SQLModel, table=True):
    __tablename__ = "password_reset_tokens"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="usuarios.id", index=True)
    token_hash: str = Field(index=True, unique=True, max_length=64)
    issued_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    expires_at: datetime = Field(index=True)
    used_at: Optional[datetime] = Field(default=None, index=True)
