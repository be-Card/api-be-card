from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Configuración de la aplicación"""
    
    # Configuración de la base de datos
    database_url: str = "postgresql://becard_user:becard_password@localhost:5432/becard_db"
    
    # Configuración de la aplicación
    app_name: str = "BeCard API"
    app_version: str = "1.0.0"
    debug: bool = True
    
    # Configuración del servidor
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Configuración JWT
    secret_key: str = "your-secret-key-change-this-in-production-make-it-very-long-and-random"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )


# Instancia global de configuración
settings = Settings()