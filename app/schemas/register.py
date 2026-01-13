from typing import Optional

from pydantic import BaseModel

from app.models.user_extended import UsuarioRead


class RegisterResponse(BaseModel):
    message: str
    user: UsuarioRead
    verification_link: Optional[str] = None
    verification_expires_at: Optional[str] = None

