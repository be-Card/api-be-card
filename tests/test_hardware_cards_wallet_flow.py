from datetime import date
from decimal import Decimal

from sqlmodel import Session, select


def _seed_minimal_auth_data(session: Session) -> None:
    from app.models.user_extended import TipoRolUsuario, TipoNivelUsuario

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

    tenant = Tenant(nombre="Tenant Test", slug="tenant-test", creado_por=owner_user_id)
    session.add(tenant)
    session.commit()
    session.refresh(tenant)

    session.add(TenantUser(tenant_id=tenant.id, user_id=owner_user_id, rol="owner"))
    session.commit()
    return tenant


def _login(client, *, email: str, password: str) -> str:
    login = client.post("/api/v1/auth/login-json", json={"email": email, "password": password})
    assert login.status_code == 200
    return login.json()["access_token"]


def test_cards_bind_lookup_and_conflict(client, db_session: Session):
    _seed_minimal_auth_data(db_session)
    socio = _create_verified_user(db_session, email="socio@example.com", password="StrongPass1!", tenant_id=None, role_tipo="socio")
    tenant = _create_tenant(db_session, owner_user_id=socio.id)

    client_user = _create_verified_user(
        db_session, email="cliente@example.com", password="StrongPass1!", tenant_id=tenant.id, role_tipo="usuario"
    )

    token = _login(client, email=socio.email, password="StrongPass1!")
    uid = "UID-TEST-123"

    bind = client.post(
        "/api/v1/cards/bind",
        headers={"Authorization": f"Bearer {token}"},
        json={"uid": uid, "codigo_cliente": client_user.codigo_cliente},
    )
    assert bind.status_code == 201

    lookup = client.post("/api/v1/cards/lookup", headers={"Authorization": f"Bearer {token}"}, json={"uid": uid})
    assert lookup.status_code == 200
    body = lookup.json()
    assert body["card_status"] == "assigned_user"
    assert body["user_id"] == client_user.id
    assert body["balance"] == "0.00"

    other_client = _create_verified_user(
        db_session, email="cliente2@example.com", password="StrongPass1!", tenant_id=tenant.id, role_tipo="usuario"
    )
    conflict = client.post(
        "/api/v1/cards/bind",
        headers={"Authorization": f"Bearer {token}"},
        json={"uid": uid, "codigo_cliente": other_client.codigo_cliente},
    )
    assert conflict.status_code == 409


def test_anonymous_issue_topup_and_lookup_balance(client, db_session: Session):
    _seed_minimal_auth_data(db_session)
    socio = _create_verified_user(db_session, email="socio2@example.com", password="StrongPass1!", tenant_id=None, role_tipo="socio")
    _create_tenant(db_session, owner_user_id=socio.id)

    token = _login(client, email=socio.email, password="StrongPass1!")
    uid = "UID-ANON-1"

    issue = client.post("/api/v1/cards/issue-anonymous", headers={"Authorization": f"Bearer {token}"}, json={"uid": uid})
    assert issue.status_code == 201
    card_id = issue.json()["card_id"]

    topup = client.post(
        f"/api/v1/wallets/anonymous/{card_id}/topup",
        headers={"Authorization": f"Bearer {token}"},
        json={"amount": "1000.00"},
    )
    assert topup.status_code == 201

    lookup = client.post("/api/v1/cards/lookup", headers={"Authorization": f"Bearer {token}"}, json={"uid": uid})
    assert lookup.status_code == 200
    body = lookup.json()
    assert body["card_status"] == "anonymous_wallet"
    assert Decimal(body["balance"]) == Decimal("1000.00")


def test_device_session_wallet_creates_sale_and_debits_wallet(client, db_session: Session):
    from app.models.sales_point import PuntoVenta, Equipo
    from app.models.beer import Cerveza, PrecioCerveza
    from app.models.wallet import Wallet

    _seed_minimal_auth_data(db_session)
    _seed_equipment_support_tables(db_session)
    socio = _create_verified_user(db_session, email="socio3@example.com", password="StrongPass1!", tenant_id=None, role_tipo="socio")
    tenant = _create_tenant(db_session, owner_user_id=socio.id)

    customer = _create_verified_user(
        db_session, email="cliente3@example.com", password="StrongPass1!", tenant_id=tenant.id, role_tipo="usuario"
    )

    beer = Cerveza(nombre="Beer", tipo="IPA", proveedor="Prov", activo=True, destacado=False, stock_base=0, tenant_id=tenant.id, creado_por=socio.id)
    db_session.add(beer)
    db_session.commit()
    db_session.refresh(beer)
    db_session.add(PrecioCerveza(id_cerveza=beer.id, precio=Decimal("1000.00"), creado_por=socio.id))
    db_session.commit()

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
    db_session.add(pv)
    db_session.commit()
    db_session.refresh(pv)

    equipo = Equipo(id_estado_equipo=1, id_barril=1, capacidad_actual=10, id_punto_de_venta=pv.id, id_cerveza=beer.id, activo=True)
    db_session.add(equipo)
    db_session.commit()
    db_session.refresh(equipo)

    uid = "UID-WALLET-USER"
    token = _login(client, email=socio.email, password="StrongPass1!")
    bind = client.post(
        "/api/v1/cards/bind",
        headers={"Authorization": f"Bearer {token}"},
        json={"uid": uid, "codigo_cliente": customer.codigo_cliente},
    )
    assert bind.status_code == 201

    wallet = Wallet(tenant_id=tenant.id, owner_type="user", owner_user_id=customer.id, balance=Decimal("1000.00"), activo=True)
    db_session.add(wallet)
    db_session.commit()
    db_session.refresh(wallet)

    create_sess = client.post(
        "/api/v1/device/sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={"equipo_id": equipo.id, "uid": uid, "requested_ml": 500, "payment_mode": "wallet"},
    )
    assert create_sess.status_code == 201
    session_id = create_sess.json()["session_id"]
    assert int(create_sess.json()["max_ml"]) == 500

    complete = client.post(
        f"/api/v1/device/sessions/{session_id}/complete",
        headers={"Authorization": f"Bearer {token}"},
        json={"poured_ml": 500},
    )
    assert complete.status_code == 200
    assert complete.json()["status"] == "completed"
    assert Decimal(str(complete.json()["final_amount"])) == Decimal("500.00")

    db_session.refresh(wallet)
    refreshed_wallet = db_session.exec(select(Wallet).where(Wallet.id == wallet.id)).first()
    assert refreshed_wallet is not None
    assert Decimal(str(refreshed_wallet.balance)) == Decimal("500.00")


def test_external_payment_confirm_and_claim_flow(client, db_session: Session):
    from app.models.sales_point import PuntoVenta, Equipo
    from app.models.beer import Cerveza, PrecioCerveza
    from app.models.points import ReglaConversionPuntos
    from app.models.sales import Venta
    from app.models.transactions import Pago, TipoEstadoPago, TransaccionPuntos

    _seed_minimal_auth_data(db_session)
    _seed_equipment_support_tables(db_session)
    socio = _create_verified_user(db_session, email="socio4@example.com", password="StrongPass1!", tenant_id=None, role_tipo="socio")
    tenant = _create_tenant(db_session, owner_user_id=socio.id)

    customer = _create_verified_user(
        db_session, email="cliente4@example.com", password="StrongPass1!", tenant_id=tenant.id, role_tipo="usuario"
    )

    beer = Cerveza(nombre="Beer", tipo="IPA", proveedor="Prov", activo=True, destacado=False, stock_base=0, tenant_id=tenant.id, creado_por=socio.id)
    db_session.add(beer)
    db_session.commit()
    db_session.refresh(beer)
    db_session.add(PrecioCerveza(id_cerveza=beer.id, precio=Decimal("1000.00"), creado_por=socio.id))
    db_session.commit()

    db_session.add(ReglaConversionPuntos(monto_minimo=Decimal("0.00"), puntos_por_peso=Decimal("1.00"), activo=True))
    db_session.commit()

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
    db_session.add(pv)
    db_session.commit()
    db_session.refresh(pv)

    equipo = Equipo(id_estado_equipo=1, id_barril=1, capacidad_actual=10, id_punto_de_venta=pv.id, id_cerveza=beer.id, activo=True)
    db_session.add(equipo)
    db_session.commit()
    db_session.refresh(equipo)

    uid = "UID-EXT-USER"
    token_socio = _login(client, email=socio.email, password="StrongPass1!")
    bind = client.post(
        "/api/v1/cards/bind",
        headers={"Authorization": f"Bearer {token_socio}"},
        json={"uid": uid, "codigo_cliente": customer.codigo_cliente},
    )
    assert bind.status_code == 201

    create_sess = client.post(
        "/api/v1/device/sessions",
        headers={"Authorization": f"Bearer {token_socio}"},
        json={"equipo_id": equipo.id, "uid": uid, "requested_ml": 500, "payment_mode": "external"},
    )
    assert create_sess.status_code == 201
    session_id = create_sess.json()["session_id"]

    complete = client.post(
        f"/api/v1/device/sessions/{session_id}/complete",
        headers={"Authorization": f"Bearer {token_socio}"},
        json={"poured_ml": 500, "payment_method_name": "Mercado Pago", "provider_transaction_id": "tx-123"},
    )
    assert complete.status_code == 200

    confirm = client.post(
        "/api/v1/payments/confirm",
        headers={"Authorization": f"Bearer {token_socio}"},
        json={"provider_transaction_id": "tx-123", "status": "aprobado"},
    )
    assert confirm.status_code == 200

    pago = db_session.exec(select(Pago).where(Pago.id_transaccion_proveedor == "tx-123")).first()
    assert pago is not None
    assert pago.estado == TipoEstadoPago.APROBADO

    tx = db_session.exec(select(TransaccionPuntos).where(TransaccionPuntos.id_usuario == customer.id)).first()
    assert tx is not None

    anon_sess = client.post(
        "/api/v1/device/sessions",
        headers={"Authorization": f"Bearer {token_socio}"},
        json={"equipo_id": equipo.id, "requested_ml": 500, "payment_mode": "external"},
    )
    assert anon_sess.status_code == 201
    anon_session_id = anon_sess.json()["session_id"]
    client.post(
        f"/api/v1/device/sessions/{anon_session_id}/complete",
        headers={"Authorization": f"Bearer {token_socio}"},
        json={"poured_ml": 500, "payment_method_name": "Mercado Pago", "provider_transaction_id": "tx-claim"},
    )
    client.post(
        "/api/v1/payments/confirm",
        headers={"Authorization": f"Bearer {token_socio}"},
        json={"provider_transaction_id": "tx-claim", "status": "aprobado"},
    )

    venta_claim = db_session.exec(select(Venta).where(Venta.id_usuario == None).order_by(Venta.fecha_hora.desc())).first()
    assert venta_claim is not None

    token_customer = _login(client, email=customer.email, password="StrongPass1!")
    claim = client.post(
        f"/api/v1/sales/{venta_claim.id_ext}/claim",
        headers={"Authorization": f"Bearer {token_customer}"},
    )
    assert claim.status_code == 200
