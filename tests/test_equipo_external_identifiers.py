from datetime import date
from decimal import Decimal

from sqlmodel import Session


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


def test_equipo_codes_backfill_and_lookup_endpoints(client, db_session: Session):
    from app.models.sales_point import PuntoVenta, Equipo
    from app.services.equipos import EquipoService

    _seed_minimal_auth_data(db_session)
    _seed_equipment_support_tables(db_session)

    socio = _create_verified_user(db_session, email="socio-eq@example.com", password="StrongPass1!", tenant_id=None, role_tipo="socio")
    tenant = _create_tenant(db_session, owner_user_id=socio.id)

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

    equipo = Equipo(id_estado_equipo=1, id_barril=1, capacidad_actual=10, id_punto_de_venta=pv.id, id_cerveza=None, activo=True)
    db_session.add(equipo)
    db_session.commit()
    db_session.refresh(equipo)

    result = EquipoService.backfill_codigos(db_session, tenant_id=tenant.id)
    assert result["puntos_venta_actualizados"] >= 1
    assert result["equipos_actualizados"] >= 1

    db_session.refresh(pv)
    db_session.refresh(equipo)
    assert pv.codigo_punto_venta is not None
    assert pv.codigo_punto_venta.startswith("PV-")
    assert equipo.tenant_id == tenant.id
    assert equipo.codigo_equipo is not None
    assert equipo.codigo_equipo.startswith("EQ-")

    token = _login(client, email=socio.email, password="StrongPass1!")

    by_id_ext = client.get(
        f"/api/v1/equipos/by-id-ext/{equipo.id_ext}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert by_id_ext.status_code == 200
    assert by_id_ext.json()["codigo_equipo"] == equipo.codigo_equipo

    by_code = client.get(
        f"/api/v1/equipos/by-code/{equipo.codigo_equipo}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert by_code.status_code == 200
    assert by_code.json()["id"] == equipo.id


def test_device_session_accepts_equipo_id_ext_or_code(client, db_session: Session):
    from app.models.sales_point import PuntoVenta, Equipo
    from app.models.beer import Cerveza, PrecioCerveza
    from app.services.equipos import EquipoService

    _seed_minimal_auth_data(db_session)
    _seed_equipment_support_tables(db_session)

    socio = _create_verified_user(db_session, email="socio-eq2@example.com", password="StrongPass1!", tenant_id=None, role_tipo="socio")
    tenant = _create_tenant(db_session, owner_user_id=socio.id)

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

    EquipoService.backfill_codigos(db_session, tenant_id=tenant.id)
    db_session.refresh(equipo)

    token = _login(client, email=socio.email, password="StrongPass1!")

    by_id_ext = client.post(
        "/api/v1/device/sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={"equipo_id_ext": str(equipo.id_ext), "requested_ml": 500, "payment_mode": "external"},
    )
    assert by_id_ext.status_code == 201

    by_code = client.post(
        "/api/v1/device/sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={"equipo_codigo": equipo.codigo_equipo, "requested_ml": 500, "payment_mode": "external"},
    )
    assert by_code.status_code == 201

