"""
Esquemas Pydantic para autenticación
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class Token(BaseModel):
    """Esquema para token de acceso y refresh"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # segundos
    refresh_token: Optional[str] = None  # Token para renovar el access_token


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


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10)
    new_password: str = Field(min_length=1)


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=10)


class ResendVerificationRequest(BaseModel):
    email: EmailStr
