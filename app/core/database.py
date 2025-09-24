from sqlmodel import SQLModel, create_engine, Session
from app.core.config import settings

# Crear el motor de la base de datos
engine = create_engine(
    settings.database_url,
    echo=settings.debug,  # Mostrar consultas SQL en modo debug
    pool_pre_ping=True,   # Verificar conexiones antes de usarlas
)


def create_db_and_tables():
    """Crear todas las tablas en la base de datos"""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Generador de sesiones de base de datos"""
    with Session(engine) as session:
        yield session