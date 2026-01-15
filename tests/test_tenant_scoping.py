from datetime import date

from sqlmodel import Session


def _seed_minimal_auth_data(session: Session) -> None:
    from app.models.user_extended import TipoRolUsuario, TipoNivelUsuario, UsuarioRol

    if session.get(TipoRolUsuario, 1) is None:
        session.add(TipoRolUsuario(id=1, tipo="usuario", descripcion="Usuario básico"))
    if session.get(TipoRolUsuario, 2) is None:
        session.add(TipoRolUsuario(id=2, tipo="socio", descripcion="Socio"))
    if session.get(TipoNivelUsuario, 1) is None:
        session.add(
            TipoNivelUsuario(
                id=1,
                nivel="Bronce",
                puntaje_min=0,
                puntaje_max=999999,
                beneficios=None,
            )
        )
    session.commit()


def _create_verified_user(session: Session, *, email: str, password: str):
    from app.services.users import UserService
    from app.models.user_extended import UsuarioRol

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
    )
    user.verificado = True
    session.add(user)
    session.commit()
    session.refresh(user)

    session.add(UsuarioRol(id_usuario=user.id, id_rol=2))
    session.commit()
    return user


def _seed_equipment_support_tables(session: Session) -> None:
    from app.models.sales_point import TipoBarril, TipoEstadoEquipo

    if session.get(TipoEstadoEquipo, 1) is None:
        session.add(TipoEstadoEquipo(id=1, estado="Activo", permite_ventas=True))
    if session.get(TipoBarril, 1) is None:
        session.add(TipoBarril(id=1, capacidad=30, nombre="30L"))
    session.commit()


def test_tenants_me_and_cross_tenant_forbidden(client, db_session: Session):
    from app.models.tenant import Tenant, TenantUser

    _seed_minimal_auth_data(db_session)
    user1 = _create_verified_user(db_session, email="u1@example.com", password="StrongPass1!")
    user2 = _create_verified_user(db_session, email="u2@example.com", password="StrongPass1!")

    tenant1 = Tenant(nombre="Tenant 1", slug="tenant-1", creado_por=user1.id)
    tenant2 = Tenant(nombre="Tenant 2", slug="tenant-2", creado_por=user2.id)
    db_session.add(tenant1)
    db_session.add(tenant2)
    db_session.commit()
    db_session.refresh(tenant1)
    db_session.refresh(tenant2)

    db_session.add(TenantUser(tenant_id=tenant1.id, user_id=user1.id, rol="owner"))
    db_session.add(TenantUser(tenant_id=tenant2.id, user_id=user2.id, rol="owner"))
    db_session.commit()

    login = client.post("/api/v1/auth/login-json", json={"email": user1.email, "password": "StrongPass1!"})
    assert login.status_code == 200
    token = login.json()["access_token"]

    me_tenants = client.get("/api/v1/tenants/me", headers={"Authorization": f"Bearer {token}"})
    assert me_tenants.status_code == 200
    assert [t["slug"] for t in me_tenants.json()] == ["tenant-1"]

    assert me_tenants.json()[0]["nombre"] == "Tenant 1"


def test_equipos_puntos_venta_is_tenant_scoped(client, db_session: Session):
    from app.models.tenant import Tenant, TenantUser
    from app.models.sales_point import PuntoVenta, Equipo

    _seed_minimal_auth_data(db_session)
    _seed_equipment_support_tables(db_session)

    user1 = _create_verified_user(db_session, email="u3@example.com", password="StrongPass1!")
    user2 = _create_verified_user(db_session, email="u4@example.com", password="StrongPass1!")

    tenant1 = Tenant(nombre="Tenant A", slug="tenant-a", creado_por=user1.id)
    tenant2 = Tenant(nombre="Tenant B", slug="tenant-b", creado_por=user2.id)
    db_session.add(tenant1)
    db_session.add(tenant2)
    db_session.commit()
    db_session.refresh(tenant1)
    db_session.refresh(tenant2)

    db_session.add(TenantUser(tenant_id=tenant1.id, user_id=user1.id, rol="owner"))
    db_session.add(TenantUser(tenant_id=tenant2.id, user_id=user2.id, rol="owner"))
    db_session.commit()

    pv1 = PuntoVenta(
        nombre="PV A",
        calle="Calle",
        altura=123,
        localidad="Loc",
        provincia="Prov",
        id_usuario_socio=user1.id,
        tenant_id=tenant1.id,
    )
    pv2 = PuntoVenta(
        nombre="PV B",
        calle="Calle",
        altura=456,
        localidad="Loc",
        provincia="Prov",
        id_usuario_socio=user2.id,
        tenant_id=tenant2.id,
    )
    db_session.add(pv1)
    db_session.add(pv2)
    db_session.commit()
    db_session.refresh(pv1)
    db_session.refresh(pv2)

    db_session.add(
        Equipo(id_estado_equipo=1, id_barril=1, capacidad_actual=10, id_punto_de_venta=pv1.id, id_cerveza=None)
    )
    db_session.add(
        Equipo(id_estado_equipo=1, id_barril=1, capacidad_actual=10, id_punto_de_venta=pv2.id, id_cerveza=None)
    )
    db_session.commit()

    login = client.post("/api/v1/auth/login-json", json={"email": user1.email, "password": "StrongPass1!"})
    assert login.status_code == 200
    token = login.json()["access_token"]

    puntos = client.get("/api/v1/equipos/puntos-venta", headers={"Authorization": f"Bearer {token}"})
    assert puntos.status_code == 200
    assert [p["nombre"] for p in puntos.json()] == ["PV A"]

    forbidden = client.get(
        "/api/v1/equipos/puntos-venta",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-Slug": "tenant-b"},
    )
    assert forbidden.status_code == 403
