import os

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DEBUG", "false")
os.environ.setdefault("SQL_ECHO", "false")
os.environ.setdefault("AUTO_CREATE_DB", "false")

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import app.core.database
from app.core.rate_limit import limiter

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

limiter.enabled = False


@pytest.fixture()
def engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


@pytest.fixture()
def db_session(engine):
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture()
def client(engine, db_session):
    from app.main import app
    from app.core.database import get_session

    def get_session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_session_override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
