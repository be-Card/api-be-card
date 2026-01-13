import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine, select
from sqlalchemy.pool import StaticPool
from datetime import datetime, timedelta
from decimal import Decimal

from app.routers import pricing as pricing_router
from app.core.database import get_session
from app.routers.auth import require_admin, require_admin_or_socio, get_current_user
from app.models import Cerveza, PrecioCerveza, Usuario


class DummyUser:
    def __init__(self, id: int = 1):
        self.id = id
        self.activo = True


@pytest.fixture()
def engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Import all SQLModel tables
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture()
def app(engine):
    app = FastAPI()
    # Include router with API prefix like real app
    app.include_router(pricing_router.router, prefix="/api/v1")

    # Dependency overrides
    def get_test_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    app.dependency_overrides[require_admin] = lambda: DummyUser(1)
    app.dependency_overrides[require_admin_or_socio] = lambda: DummyUser(1)
    app.dependency_overrides[get_current_user] = lambda: DummyUser(1)

    return app


@pytest.fixture()
def client(app):
    return TestClient(app)


def seed_beer_with_price(engine) -> int:
    """Create a beer and a current price in the test DB, return beer id"""
    with Session(engine) as session:
        # Ensure a user exists if SQLite enforces foreign keys (usually off)
        # Minimal Usuario row; fill only required fields if needed
        user = Usuario(
            codigo_cliente="TESTCODE1234567890",
            nombres="Test",
            apellidos="User",
        )
        session.add(user)
        session.flush()

        cerveza = Cerveza(
            nombre="Test IPA",
            tipo="IPA",
            proveedor="Acme",
            activo=True,
            destacado=False,
        )
        session.add(cerveza)
        session.flush()

        precio = PrecioCerveza(
            id_cerveza=cerveza.id,
            precio=Decimal("100.00"),
            creado_por=user.id or 1,
            motivo="Precio inicial",
        )
        session.add(precio)
        session.commit()
        return cerveza.id


def test_create_regla_and_calcular_precio_happy(app, client, engine):
    beer_id = seed_beer_with_price(engine)

    now = datetime.utcnow()

    # Create a 10% discount rule for the beer
    create_payload = {
        "nombre": "Promo 10",
        "descripcion": "10% off",
        "precio": None,
        "esta_activo": True,
        "prioridad": "media",
        "multiplicador": 0.9,
        "fecha_hora_inicio": now.isoformat(),
        "fecha_hora_fin": None,
        "dias_semana": None,
        "cervezas_ids": [beer_id],
        "puntos_venta_ids": None,
        "equipos_ids": None,
    }

    resp = client.post("/api/v1/pricing/reglas", json=create_payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["nombre"] == "Promo 10"
    assert data["vigente"] is True

    # Calculate price for the beer
    calc_payload = {
        "id_cerveza": beer_id,
        "cantidad": 1,
    }
    resp2 = client.post("/api/v1/pricing/calcular", json=calc_payload)
    assert resp2.status_code == 200, resp2.text
    calc = resp2.json()
    assert str(calc["precio_base"]) == "100.00"
    # 10% discount via multiplicador 0.9 => 90.00
    assert str(calc["precio_final"]) in ("90.00", "90")
    assert "Promo 10" in calc["reglas_aplicadas"]


def test_get_regla_not_found(client):
    resp = client.get("/api/v1/pricing/reglas/99999")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Regla no encontrada"


def test_calcular_precio_not_found_base_price(client):
    # Beer id doesn't exist in DB, base price missing
    calc_payload = {
        "id_cerveza": 99999,
        "cantidad": 1,
    }
    resp = client.post("/api/v1/pricing/calcular", json=calc_payload)
    assert resp.status_code == 404
    assert "Precio base no encontrado" in resp.json()["detail"]
