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
        session.add(TipoNivelUsuario(id=1, nivel="Bronce", puntaje_min=0, puntaje_max=999999, beneficios=None))
    session.commit()


def _seed_equipment_support_tables(session: Session) -> None:
    from app.models.sales_point import TipoBarril, TipoEstadoEquipo

    if session.get(TipoEstadoEquipo, 1) is None:
        session.add(TipoEstadoEquipo(id=1, estado="Activo", permite_ventas=True))
    if session.get(TipoBarril, 1) is None:
        session.add(TipoBarril(id=1, capacidad=30, nombre="30L"))
    session.commit()


def _create_verified_user(session: Session, *, email: str, password: str, tenant_id: int | None, role_tipo: str):
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


def _login(client, *, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/login-json", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def _seed_terminal_fixture(session: Session):
    from app.models.beer import Cerveza, PrecioCerveza
    from app.models.sales_point import Equipo, PuntoVenta
    from app.models.terminal import TerminalRegistro, TerminalRegistroCreate
    from app.services.terminales import TerminalService

    _seed_minimal_auth_data(session)
    _seed_equipment_support_tables(session)

    socio = _create_verified_user(
        session,
        email="socio-qr@example.com",
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

    punto_venta = PuntoVenta(
        nombre="Taproom",
        calle="Calle",
        altura=100,
        localidad="Ciudad",
        provincia="Provincia",
        id_usuario_socio=socio.id,
        tenant_id=tenant.id,
        activo=True,
    )
    session.add(punto_venta)
    session.commit()
    session.refresh(punto_venta)

    equipo = Equipo(
        id_estado_equipo=1,
        id_barril=1,
        capacidad_actual=20,
        id_punto_de_venta=punto_venta.id,
        id_cerveza=beer.id,
        activo=True,
    )
    session.add(equipo)
    session.commit()
    session.refresh(equipo)

    terminal_read, _ = TerminalService.registrar_terminal(
        session,
        data=TerminalRegistroCreate(
            nombre="Pantalla 1",
            descripcion=None,
            equipo_id=equipo.id,
            punto_venta_id=punto_venta.id,
            hardware_id=None,
            firmware_version=None,
        ),
        tenant_id=tenant.id,
        user_id=socio.id,
    )
    terminal = session.get(TerminalRegistro, terminal_read.id)
    assert terminal is not None
    return socio, tenant, terminal


def test_terminal_checkout_creates_screen_session_and_payment(client, db_session: Session, monkeypatch):
    from app.services.payment_gateway import QRPaymentResult

    socio, tenant, terminal = _seed_terminal_fixture(db_session)
    token = _login(client, email=socio.email, password="StrongPass1!")
    published_commands: list[dict] = []

    class DummyResponse:
        status_code = 200

        def raise_for_status(self):
            return None

    def fake_post(*args, **kwargs):
        published_commands.append(kwargs["json"])
        return DummyResponse()

    class DummyGateway:
        def create_qr_payment(self, **kwargs):
            assert kwargs["amount"] == Decimal("1200.00")
            return QRPaymentResult(
                qr_data="https://mercadopago.test/checkout/abc",
                provider_payment_id="mp-pref-1",
                external_reference=kwargs["external_reference"],
            )

    monkeypatch.setattr("app.services.terminal_checkout.httpx.post", fake_post)
    monkeypatch.setattr("app.services.terminal_checkout.get_payment_gateway", lambda: DummyGateway())

    create_response = client.post(
        f"/api/v1/terminal-checkout/terminales/{terminal.id_ext}/sessions",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-Slug": tenant.slug},
    )
    assert create_response.status_code == 201
    body = create_response.json()
    assert body["terminal_nombre"] == terminal.nombre
    assert body["cerveza_nombre"] == "Golden QR"
    assert body["checkout_url"].endswith(body["session_id"])

    payment_response = client.post(
        f"/api/v1/terminal-checkout/public/{body['session_id']}/payments",
        json={"requested_ml": 500},
    )
    assert payment_response.status_code == 200
    payment_body = payment_response.json()
    assert payment_body["status"] == "pending_payment"
    assert payment_body["payment_flow"] == "redirect"
    assert payment_body["provider_payment_id"] == "mp-pref-1"
    assert Decimal(payment_body["requested_amount"]) == Decimal("1200.00")
    assert len(published_commands) == 1
    assert published_commands[0]["command_type"] == "render_checkout_qr"


def test_terminal_checkout_payment_requires_amount_or_volume(client, db_session: Session, monkeypatch):
    socio, tenant, terminal = _seed_terminal_fixture(db_session)
    token = _login(client, email=socio.email, password="StrongPass1!")

    class DummyResponse:
        status_code = 200

        def raise_for_status(self):
            return None

    monkeypatch.setattr("app.services.terminal_checkout.httpx.post", lambda *args, **kwargs: DummyResponse())

    create_response = client.post(
        f"/api/v1/terminal-checkout/terminales/{terminal.id_ext}/sessions",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-Slug": tenant.slug},
    )
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    payment_response = client.post(
        f"/api/v1/terminal-checkout/public/{session_id}/payments",
        json={},
    )
    assert payment_response.status_code == 400
    assert payment_response.json()["detail"] == "Tenés que indicar mililitros o monto"


def test_mercadopago_webhook_approves_terminal_checkout_and_sends_payment_confirmed(client, db_session: Session, monkeypatch):
    from app.models.terminal_checkout import TerminalCheckoutSession
    from app.services.payment_gateway import WebhookPaymentData

    socio, tenant, terminal = _seed_terminal_fixture(db_session)
    token = _login(client, email=socio.email, password="StrongPass1!")

    published_commands: list[dict] = []

    class DummyResponse:
        status_code = 200

        def raise_for_status(self):
            return None

    def fake_post(*args, **kwargs):
        published_commands.append(kwargs["json"])
        return DummyResponse()

    monkeypatch.setattr("app.services.terminal_checkout.httpx.post", fake_post)
    monkeypatch.setattr("app.routers.webhooks.httpx.post", fake_post)
    monkeypatch.setattr("app.routers.webhooks.engine", db_session.get_bind())

    create_response = client.post(
        f"/api/v1/terminal-checkout/terminales/{terminal.id_ext}/sessions",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-Slug": tenant.slug},
    )
    session_id = create_response.json()["session_id"]

    checkout_session = db_session.exec(
        select(TerminalCheckoutSession).where(TerminalCheckoutSession.id_ext == UUID(session_id))
    ).first()
    assert checkout_session is not None
    checkout_session.status = "pending_payment"
    checkout_session.requested_ml = 500
    checkout_session.requested_amount = Decimal("1200.00")
    db_session.add(checkout_session)
    db_session.commit()

    class DummyGateway:
        def verify_webhook_signature(self, headers, body):
            return True

        def parse_webhook(self, headers, body):
            return WebhookPaymentData(
                provider_payment_id="mp-pay-123",
                external_reference=session_id,
                status="approved",
                amount=Decimal("1200.00"),
            )

    monkeypatch.setattr("app.services.payment_gateway.get_payment_gateway", lambda gateway_name=None: DummyGateway())

    webhook_response = client.post("/api/v1/webhooks/mercadopago", json={"type": "payment"})
    assert webhook_response.status_code == 200

    refreshed = db_session.exec(
        select(TerminalCheckoutSession).where(TerminalCheckoutSession.id_ext == UUID(session_id))
    ).first()
    assert refreshed is not None
    assert refreshed.status == "approved"
    assert refreshed.provider_payment_id == "mp-pay-123"
    assert refreshed.approved_at is not None
    assert published_commands[-1]["command_type"] == "payment_confirmed"
    payload = published_commands[-1]["payload"]
    assert "approved" in payload
    assert "1200.00" in payload
