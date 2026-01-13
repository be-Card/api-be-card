from datetime import date, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class UserProfessionalInfo(SQLModel, table=True):
    __tablename__ = "user_professional_info"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="usuarios.id", unique=True, index=True)

    puesto: Optional[str] = Field(default=None, max_length=100)
    departamento: Optional[str] = Field(default=None, max_length=100)
    fecha_ingreso: Optional[date] = Field(default=None)
    id_empleado: Optional[str] = Field(default=None, max_length=50)

    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)

