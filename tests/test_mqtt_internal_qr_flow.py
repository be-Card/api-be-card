from datetime import date
from decimal import Decimal

from sqlmodel import Session, select


def _seed_minimal_auth_data(session: Session) -> None:
    from app.models.user_extended import TipoNivelUsuario, TipoRolUsuario

    if session.get(TipoRolUsuario, 1) is None:
        session.add(TipoRolUsuario(id=1, tipo="usuario", descripcion="Usuario"))
    if session.get(TipoRolUsuario, 2) is None:
        session.add(TipoRolUsuario(id=2, tipo="socio", descripcion="Socio"))
    if session.get(TipoNivelUsuario, 1) is None:
        session.add(
            TipoNivelUsuario(
                id=1, nivel="Bronce", puntaje_min=0, puntaje_max=999999, beneficios=None
            )
        )
    session.commit()


def _seed_equipment_support_tables(session: Session) -> None:
    from app.models.sales_point import TipoBarril, TipoEstadoEquipo

    if session.get(TipoEstadoEquipo, 1) is None:
        session.add(TipoEstadoEquipo(id=1, estado="Activo", permite_ventas=True))
    if session.get(TipoBarril, 1) is None:
        session.add(TipoBarril(id=1, capacidad=30, nombre="30L"))
    session.commit()


def _create_verified_user(
    session: Session, *, email: str, password: str, tenant_id: int | None, role_tipo: str
):
    from app.models.tenant import TenantUser
    from app.services.users import UserService

    user = UserService.create_user(
        session=session,
        nombre_usuario=email.split("@", 1)[0],
        email=email,
        password=password,
        nombre="Test",
        apellido="User",
        sexo="M",
        fecha_nacimiento=date(1990, 1, 1),
        telefono=None,
        tenant_id=tenant_id,
        role_tipo=role_tipo,
    )
    user.verificado = True
    session.add(user)
    session.commit()
    session.refresh(user)

    if tenant_id is not None:
        session.add(TenantUser(tenant_id=tenant_id, user_id=user.id, rol="member"))
        session.commit()
    return user


def _create_tenant(session: Session, *, owner_user_id: int):
    from app.models.tenant import Tenant, TenantUser

    tenant = Tenant(nombre="Tenant QR", slug="tenant-qr", creado_por=owner_user_id)
    session.add(tenant)
    session.commit()
    session.refresh(tenant)

    session.add(TenantUser(tenant_id=tenant.id, user_id=owner_user_id, rol="owner"))
    session.commit()
    return tenant


def _seed_terminal(session: Session):
    from app.models.beer import Cerveza, PrecioCerveza
    from app.models.sales_point import Equipo, PuntoVenta
    from app.models.terminal import TerminalRegistroCreate
    from app.services.terminales import TerminalService

    _seed_minimal_auth_data(session)
    _seed_equipment_support_tables(session)

    socio = _create_verified_user(
        session,
        email="socio-mqtt-qr@example.com",
        password="StrongPass1!",
        tenant_id=None,
        role_tipo="socio",
    )
    tenant = _create_tenant(session, owner_user_id=socio.id)

    beer = Cerveza(
        nombre="Golden QR",
        tipo="Golden",
        proveedor="Prov",
        activo=True,
        destacado=False,
        stock_base=0,
        tenant_id=tenant.id,
        creado_por=socio.id,
    )
    session.add(beer)
    session.commit()
    session.refresh(beer)
    session.add(PrecioCerveza(id_cerveza=beer.id, precio=Decimal("2400.00"), creado_por=socio.id))
    session.commit()

    pv = PuntoVenta(
        nombre="PV",
        calle="Calle",
        altura=123,
        localidad="Loc",
        provincia="Prov",
        id_usuario_socio=socio.id,
        tenant_id=tenant.id,
        activo=True,
    )
    session.add(pv)
    session.commit()
    session.refresh(pv)

    equipo = Equipo(
        id_estado_equipo=1,
        id_barril=1,
        capacidad_actual=10,
        id_punto_de_venta=pv.id,
        id_cerveza=beer.id,
        activo=True,
    )
    session.add(equipo)
    session.commit()
    session.refresh(equipo)

    terminal_read, _ = TerminalService.registrar_terminal(
        session,
        data=TerminalRegistroCreate(
            nombre="Pantalla MQTT",
            descripcion=None,
            equipo_id=equipo.id,
            punto_venta_id=pv.id,
            hardware_id=None,
            firmware_version=None,
        ),
        tenant_id=tenant.id,
        user_id=socio.id,
    )
    return tenant, terminal_read


def test_mqtt_qr_checkout_start_sends_render_checkout_qr(client, db_session: Session, monkeypatch):
    from app.core.config import settings

    tenant, terminal_read = _seed_terminal(db_session)
    published: list[dict] = []

    class DummyResp:
        status_code = 200

        def raise_for_status(self):
            return None

    def fake_post(*args, **kwargs):
        published.append(kwargs["json"])
        return DummyResp()

    monkeypatch.setattr("app.services.terminal_checkout.httpx.post", fake_post)
    monkeypatch.setattr("app.routers.mqtt_internal.settings.backend_public_url", "http://testserver")

    resp = client.post(
        "/api/v1/internal/mqtt/qr/checkout-start",
        headers={"X-Internal-Token": settings.mqtt_internal_token},
        json={"terminal_id_ext": str(terminal_read.id_ext)},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["qr_data"].endswith(body["checkout_session_id"])
    assert published[-1]["command_type"] == "render_checkout_qr"


def test_mqtt_qr_session_start_and_complete_paid(client, db_session: Session):
    from app.core.config import settings
    from app.models.transactions import Pago, TipoEstadoPago

    tenant, terminal_read = _seed_terminal(db_session)

    start = client.post(
        "/api/v1/internal/mqtt/qr/session-start",
        headers={"X-Internal-Token": settings.mqtt_internal_token},
        json={
            "terminal_id_ext": str(terminal_read.id_ext),
            "requested_ml": 500,
            "idempotency_key": "qr-1",
        },
    )
    assert start.status_code == 200
    start_body = start.json()
    assert start_body["ok"] is True
    session_id = start_body["session_id"]

    complete = client.post(
        "/api/v1/internal/mqtt/qr/session-complete",
        headers={"X-Internal-Token": settings.mqtt_internal_token},
        json={
            "terminal_id_ext": str(terminal_read.id_ext),
            "session_id": session_id,
            "poured_ml": 400,
            "provider_transaction_id": "mp-pay-123",
            "payment_method_name": "MercadoPago",
        },
    )
    assert complete.status_code == 200
    complete_body = complete.json()
    assert complete_body["ok"] is True
    assert complete_body["status"] == "completed"
    assert Decimal(str(complete_body["final_amount"])) == Decimal("960.00")

    pago = db_session.exec(select(Pago).where(Pago.id_transaccion_proveedor == "mp-pay-123")).first()
    assert pago is not None
    assert pago.estado == TipoEstadoPago.APROBADO
