from sqlmodel import Field, SQLModel
from typing import Optional
from datetime import datetime


class UserPreferencesDB(SQLModel, table=True):
    __tablename__ = "user_preferences"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="usuarios.id", unique=True, index=True)

    notifications_email_sales: bool = Field(default=True)
    notifications_email_inventory: bool = Field(default=True)
    notifications_email_clients: bool = Field(default=True)
    notifications_push_critical: bool = Field(default=True)
    notifications_push_reports: bool = Field(default=True)

    language: str = Field(default="es", max_length=5)
    date_format: str = Field(default="YYYY-MM-DD", max_length=20)
    theme: str = Field(default="dark", max_length=20)

    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)

