import hashlib
import hmac
import json
from datetime import date
from decimal import Decimal
from uuid import UUID

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
        from app.models.tenant import TenantUser

        session.add(TenantUser(tenant_id=tenant_id, user_id=user.id, rol="member"))
        session.commit()
    return user


def _create_tenant(session: Session, *, owner_user_id: int):
    from app.models.tenant import Tenant, TenantUser

    tenant = Tenant(nombre="Tenant Webhook", slug="tenant-webhook", creado_por=owner_user_id)
    session.add(tenant)
    session.commit()
    session.refresh(tenant)

    session.add(TenantUser(tenant_id=tenant.id, user_id=owner_user_id, rol="owner"))
    session.commit()
    return tenant


def _seed_checkout_session(session: Session):
    from app.models.beer import Cerveza, PrecioCerveza
    from app.models.sales_point import Equipo, PuntoVenta
    from app.models.terminal import TerminalRegistroCreate
    from app.models.terminal_checkout import TerminalCheckoutSession
    from app.services.terminales import TerminalService

    _seed_minimal_auth_data(session)
    _seed_equipment_support_tables(session)

    socio = _create_verified_user(
        session,
        email="socio-order@example.com",
        password="StrongPass1!",
        tenant_id=None,
        role_tipo="socio",
    )
    tenant = _create_tenant(session, owner_user_id=socio.id)

    beer = Cerveza(
        nombre="Golden Order",
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
            nombre="Pantalla Webhook",
            descripcion=None,
            equipo_id=equipo.id,
            punto_venta_id=pv.id,
            hardware_id=None,
            firmware_version=None,
        ),
        tenant_id=tenant.id,
        user_id=socio.id,
    )

    checkout_session = TerminalCheckoutSession(
        tenant_id=tenant.id,
        terminal_id=terminal_read.id,
        equipo_id=equipo.id,
        cerveza_id=beer.id,
        status="pending_payment",
        terminal_nombre="Pantalla Webhook",
        cerveza_nombre=beer.nombre,
        cerveza_tipo=beer.tipo,
        price_per_liter=Decimal("2400.00"),
        requested_ml=500,
        requested_amount=Decimal("1200.00"),
        checkout_url="https://example.com/checkout",
        expires_at=date.today(),
    )
    session.add(checkout_session)
    session.commit()
    session.refresh(checkout_session)
    return checkout_session


def _build_signature(secret: str, data_id: str, request_id: str, ts: str) -> str:
    manifest = f"id:{data_id.lower()};request-id:{request_id};ts:{ts};"
    digest = hmac.new(secret.encode("utf-8"), manifest.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"ts={ts},v1={digest}"


def test_mercadopago_gateway_supports_order_signature_and_payload(monkeypatch):
    from app.services.mercadopago_gateway import MercadoPagoGateway

    monkeypatch.setattr("app.services.mercadopago_gateway.settings.mp_access_token", "test-token")
    monkeypatch.setattr("app.services.mercadopago_gateway.settings.mp_webhook_secret", "test-secret")

    gateway = MercadoPagoGateway()
    body_dict = {
        "action": "order.processed",
        "type": "order",
        "data": {
            "id": "ORD01JYHTJA9M4NKTA06K7M808NJD",
            "external_reference": "12345678-1234-1234-1234-123456789012",
            "status": "processed",
            "total_amount": "100.00",
            "transactions": {
                "cash_outs": [
                    {
                        "id": "CAS01JYHTJA9M4NKTA06K7N6SM4AT",
                        "reference": {"id": "116232980550"},
                        "status": "processed",
                    }
                ]
            },
        },
    }
    body = json.dumps(body_dict).encode("utf-8")
    headers = {
        "x-request-id": "2066ca19-c6f1-498a-be75-1923005edd06",
        "x-signature": _build_signature(
            "test-secret",
            "ORD01JYHTJA9M4NKTA06K7M808NJD",
            "2066ca19-c6f1-498a-be75-1923005edd06",
            "1742505638683",
        ),
    }

    assert gateway.verify_webhook_signature(headers, body) is True
    parsed = gateway.parse_webhook(headers, body)
    assert parsed.status == "approved"
    assert parsed.external_reference == "12345678-1234-1234-1234-123456789012"
    assert parsed.provider_payment_id == "116232980550"
    assert parsed.amount == Decimal("100.00")


def test_order_processed_webhook_marks_checkout_session_approved(client, db_session: Session, monkeypatch):
    from app.services.mercadopago_gateway import MercadoPagoGateway
    from app.models.terminal_checkout import TerminalCheckoutSession

    checkout_session = _seed_checkout_session(db_session)
    published_commands: list[dict] = []

    class DummyResponse:
        status_code = 200

        def raise_for_status(self):
            return None

    def fake_post(*args, **kwargs):
        published_commands.append(kwargs["json"])
        return DummyResponse()

    monkeypatch.setattr("app.services.terminal_checkout.httpx.post", fake_post)
    monkeypatch.setattr("app.routers.webhooks.engine", db_session.get_bind())
    monkeypatch.setattr("app.services.mercadopago_gateway.settings.mp_access_token", "test-token")
    monkeypatch.setattr("app.services.mercadopago_gateway.settings.mp_webhook_secret", "test-secret")

    gateway = MercadoPagoGateway()
    monkeypatch.setattr("app.services.payment_gateway.get_payment_gateway", lambda gateway_name=None: gateway)

    body_dict = {
        "action": "order.processed",
        "type": "order",
        "data": {
            "id": "ORD01JYHTJA9M4NKTA06K7M808NJD",
            "external_reference": str(checkout_session.id_ext),
            "status": "processed",
            "total_amount": "1200.00",
            "transactions": {
                "cash_outs": [
                    {
                        "id": "CAS01JYHTJA9M4NKTA06K7N6SM4AT",
                        "reference": {"id": "116232980550"},
                        "status": "processed",
                    }
                ]
            },
        },
    }
    body = json.dumps(body_dict)
    request_id = "2066ca19-c6f1-498a-be75-1923005edd06"
    signature = _build_signature(
        "test-secret",
        "ORD01JYHTJA9M4NKTA06K7M808NJD",
        request_id,
        "1742505638683",
    )

    response = client.post(
        "/api/v1/webhooks/mercadopago",
        content=body,
        headers={
            "Content-Type": "application/json",
            "x-request-id": request_id,
            "x-signature": signature,
        },
    )
    assert response.status_code == 200

    db_session.expire_all()
    refreshed = db_session.exec(
        select(TerminalCheckoutSession).where(TerminalCheckoutSession.id_ext == UUID(str(checkout_session.id_ext)))
    ).first()
    assert refreshed is not None
    assert refreshed.status == "approved"
    assert refreshed.provider_payment_id == "116232980550"
    assert published_commands[-1]["command_type"] == "payment_confirmed"


def test_order_canceled_webhook_marks_checkout_session_rejected(client, db_session: Session, monkeypatch):
    from app.services.mercadopago_gateway import MercadoPagoGateway
    from app.models.terminal_checkout import TerminalCheckoutSession

    checkout_session = _seed_checkout_session(db_session)
    published_commands: list[dict] = []

    class DummyResponse:
        status_code = 200

        def raise_for_status(self):
            return None

    def fake_post(*args, **kwargs):
        published_commands.append(kwargs["json"])
        return DummyResponse()

    monkeypatch.setattr("app.services.terminal_checkout.httpx.post", fake_post)
    monkeypatch.setattr("app.routers.webhooks.engine", db_session.get_bind())
    monkeypatch.setattr("app.services.mercadopago_gateway.settings.mp_access_token", "test-token")
    monkeypatch.setattr("app.services.mercadopago_gateway.settings.mp_webhook_secret", "test-secret")

    gateway = MercadoPagoGateway()
    monkeypatch.setattr("app.services.payment_gateway.get_payment_gateway", lambda gateway_name=None: gateway)

    body_dict = {
        "action": "order.canceled",
        "type": "order",
        "data": {
            "id": "ORD01JYHTJA9M4NKTA06K7M808NJD",
            "external_reference": str(checkout_session.id_ext),
            "status": "canceled",
            "total_amount": "1200.00",
        },
    }
    body = json.dumps(body_dict)
    request_id = "2066ca19-c6f1-498a-be75-1923005edd06"
    signature = _build_signature(
        "test-secret",
        "ORD01JYHTJA9M4NKTA06K7M808NJD",
        request_id,
        "1742505638683",
    )

    response = client.post(
        "/api/v1/webhooks/mercadopago",
        content=body,
        headers={
            "Content-Type": "application/json",
            "x-request-id": request_id,
            "x-signature": signature,
        },
    )
    assert response.status_code == 200

    db_session.expire_all()
    refreshed = db_session.exec(
        select(TerminalCheckoutSession).where(TerminalCheckoutSession.id_ext == UUID(str(checkout_session.id_ext)))
    ).first()
    assert refreshed is not None
    assert refreshed.status == "rejected"
    assert published_commands[-1]["command_type"] == "payment_rejected"
