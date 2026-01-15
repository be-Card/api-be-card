from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from app.core.config import settings as app_settings
from app.core.database import create_db_and_tables
from app.core.errors import (
    http_exception_handler,
    rate_limit_exceeded_handler,
    starlette_http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.rate_limit import limiter
from app.core.request_id import RequestIdMiddleware
from app.routers import users, auth, guests, clients, cervezas, equipos, pricing, dashboard, settings, reports, profile, tenants, admin
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

# Crear la aplicación FastAPI
app = FastAPI(
    title=app_settings.app_name,
    version=app_settings.app_version,
    description="API para BeCard - Sistema de gestión de tarjetas de presentación",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add rate limiter to app state
app.state.limiter = limiter

# Add rate limit exceeded handler
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.add_middleware(RequestIdMiddleware)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.cors_origins,
    allow_credentials=app_settings.cors_allow_credentials,
    allow_methods=app_settings.cors_allow_methods,
    allow_headers=app_settings.cors_allow_headers,
)

# Incluir routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(guests.router, prefix="/api/v1")
app.include_router(clients.router, prefix="/api/v1")
app.include_router(cervezas.router, prefix="/api/v1")
app.include_router(equipos.router, prefix="/api/v1")
app.include_router(pricing.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(settings.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(profile.router, prefix="/api/v1")
app.include_router(tenants.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")


@app.on_event("startup")
def on_startup():
    """Eventos que se ejecutan al iniciar la aplicación"""
    if app_settings.auto_create_db or app_settings.environment in ("development", "test"):
        create_db_and_tables()
        if app_settings.subscription_sweep_on_startup:
            from sqlmodel import Session
            from app.core.database import engine
            from app.services.tenants import TenantService

            with Session(engine) as session:
                TenantService.sweep_expired_subscriptions(session)


@app.get("/")
def read_root():
    """Endpoint raíz de la API"""
    return {
        "message": f"Bienvenido a {app_settings.app_name}",
        "version": app_settings.app_version,
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/health")
def health_check():
    """Endpoint para verificar el estado de la API"""
    return {"status": "healthy", "app": app_settings.app_name}
