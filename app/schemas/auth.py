"""
Esquemas Pydantic para autenticación
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class Token(BaseModel):
    """Esquema para token de acceso"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # segundos


class TokenData(BaseModel):
    """Datos extraídos del token"""
    user_id: Optional[int] = None
    email: Optional[str] = None


class LoginRequest(BaseModel):
    """Esquema para login (OAuth2 compatible)"""
    username: str = Field(description="Email o nombre de usuario")
    password: str = Field(min_length=1)


class LoginJSONRequest(BaseModel):
    """Esquema para login con JSON"""
    email: EmailStr
    password: str = Field(min_length=1)


class RefreshTokenRequest(BaseModel):
    """Esquema para renovar token"""
    refresh_token: str
