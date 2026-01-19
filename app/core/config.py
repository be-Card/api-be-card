from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional, Union, Literal
from pydantic import field_validator, model_validator, Field, AliasChoices


class Settings(BaseSettings):
    """Configuración de la aplicación"""

    environment: Literal["development", "test", "production"] = "development"

    # Configuración de la base de datos
    database_url: str

    # Configuración de la aplicación
    app_name: str = "BeCard API"
    app_version: str = "1.0.0"
    debug: bool = False
    sql_echo: bool = False
    auto_create_db: bool = False

    # Configuración del servidor
    host: str = "0.0.0.0"
    port: int = 8000

    # URL del frontend (para links de recuperación de contraseña, etc.)
    frontend_url: str = "http://localhost:5173"

    # Rol asignado al registrar usuarios vía /auth/register
    registration_default_role: str = "administrador"

    # Porcentaje de saldo (cashback) sobre el gasto total del cliente
    client_balance_rate: float = 0.05

    subscription_default_days: int = 30
    subscription_grace_days: int = 7
    subscription_sweep_on_startup: bool = True

    # Configuración CORS
    cors_origins: Union[str, List[str]] = [
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Alternative React dev server
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
    cors_allow_headers: List[str] = ["Authorization", "Content-Type", "X-Request-ID", "X-Client", "X-Tenant-Slug"]

    # Configuración JWT
    secret_key: str
    device_uid_hmac_secret: Optional[str] = None
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    algorithm: str = "HS256"
    jwt_issuer: Optional[str] = None
    jwt_audience: Optional[str] = None

    # Configuración Email
    email_backend: Literal["disabled", "smtp", "brevo"] = "disabled"
    brevo_api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("BREVO_API_KEY", "BREVO_APIKEY"),
    )
    smtp_host: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("SMTP_HOST", "BREVO_SMTP_HOST"),
    )
    smtp_port: int = Field(
        default=587,
        validation_alias=AliasChoices("SMTP_PORT", "BREVO_SMTP_PORT"),
    )
    smtp_username: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("SMTP_USERNAME", "BREVO_SMTP_USERNAME"),
    )
    smtp_password: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("SMTP_PASSWORD", "BREVO_SMTP_PASSWORD"),
    )
    smtp_from: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("SMTP_FROM", "BREVO_SMTP_FROM"),
    )
    smtp_from_email: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("SMTP_FROM_EMAIL", "BREVO_SMTP_FROM_EMAIL"),
    )
    smtp_from_name: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("SMTP_FROM_NAME", "BREVO_SMTP_FROM_NAME"),
    )
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parsea CORS_ORIGINS desde string separado por comas o lista"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @model_validator(mode="after")
    def validate_environment_settings(self):
        if self.environment == "production":
            if self.debug:
                raise ValueError("DEBUG no debe estar habilitado en producción")
            if self.sql_echo:
                raise ValueError("SQL_ECHO no debe estar habilitado en producción")
            if self.auto_create_db:
                raise ValueError("AUTO_CREATE_DB no debe estar habilitado en producción")
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )


# Instancia global de configuración
settings = Settings()
