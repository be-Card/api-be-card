from typing import Optional

from pydantic import BaseModel

from app.schemas.users import UserRead


class RegisterResponse(BaseModel):
    message: str
    user: UserRead
    verification_link: Optional[str] = None
    verification_expires_at: Optional[str] = None
