from sqlmodel import SQLModel, create_engine, Session
from app.core.config import settings

# Importar todos los modelos para que se registren en el metadata
from app.models.user_extended import Usuario, UsuarioCreate, UsuarioRead, UsuarioUpdate
from app.models.beer import (
    Cerveza, CervezaCreate, CervezaRead, CervezaUpdate,
    TipoEstiloCerveza, CervezaEstilo, PrecioCerveza,
    TipoEstiloCervezaRead, PrecioCervezaCreate, PrecioCervezaRead
)
from app.models.sales_point import (
    Equipo, EquipoCreate, EquipoRead, EquipoUpdate,
    TipoBarril, TipoEstadoEquipo, PuntoVenta,
    TipoBarrilRead, TipoEstadoEquipoRead, PuntoVentaRead,
    TipoBarrilCreate, TipoEstadoEquipoCreate, PuntoVentaCreate, PuntoVentaUpdate
)
from app.models.tenant import Tenant, TenantUser, TenantPayment
# Importar otros modelos disponibles
from app.models.refresh_token import RefreshToken
from app.models.password_reset_token import PasswordResetToken
from app.models.email_verification_token import EmailVerificationToken
from app.models.settings import UserPreferencesDB
from app.models.profile import UserProfessionalInfo
from app.models.base import *
from app.models.points import *
from app.models.pricing import *
from app.models.rewards import *
from app.models.sales import *
from app.models.transactions import *

# Crear el motor de la base de datos
engine = create_engine(
    settings.database_url,
    echo=settings.sql_echo,
    pool_pre_ping=True,   # Verificar conexiones antes de usarlas
)


def create_db_and_tables():
    """Crear todas las tablas en la base de datos"""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Generador de sesiones de base de datos"""
    with Session(engine) as session:
        yield session
