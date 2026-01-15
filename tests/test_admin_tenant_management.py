from datetime import date

from sqlmodel import Session


def _seed_roles_and_level(session: Session) -> None:
    from app.models.user_extended import TipoRolUsuario, TipoNivelUsuario

    if session.get(TipoRolUsuario, 1) is None:
        session.add(TipoRolUsuario(id=1, tipo="usuario", descripcion="Usuario básico"))
    if session.get(TipoRolUsuario, 2) is None:
        session.add(TipoRolUsuario(id=2, tipo="socio", descripcion="Socio"))
    if session.get(TipoRolUsuario, 3) is None:
        session.add(TipoRolUsuario(id=3, tipo="admin", descripcion="Admin"))
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


def _create_verified_user(session: Session, *, email: str, password: str, role_tipo: str):
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
        role_tipo=role_tipo,
    )
    user.verificado = True
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_admin_can_create_tenant_and_assign_owner(client, db_session: Session):
    _seed_roles_and_level(db_session)

    admin = _create_verified_user(db_session, email="admin@example.com", password="StrongPass1!", role_tipo="admin")
    owner = _create_verified_user(db_session, email="owner@example.com", password="StrongPass1!", role_tipo="socio")

    login = client.post("/api/v1/auth/login-json", json={"email": admin.email, "password": "StrongPass1!"})
    assert login.status_code == 200
    token = login.json()["access_token"]

    created = client.post(
        "/api/v1/tenants/admin",
        json={"nombre": "Humulus Bar", "owner_email": owner.email, "owner_rol": "owner"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert created.status_code == 201, created.text
    tenant = created.json()
    assert tenant["nombre"] == "Humulus Bar"
    assert tenant["slug"]

    login_owner = client.post("/api/v1/auth/login-json", json={"email": owner.email, "password": "StrongPass1!"})
    assert login_owner.status_code == 200
    token_owner = login_owner.json()["access_token"]

    my_tenants = client.get("/api/v1/tenants/me", headers={"Authorization": f"Bearer {token_owner}"})
    assert my_tenants.status_code == 200
    assert any(t["slug"] == tenant["slug"] for t in my_tenants.json())


def test_admin_can_add_member_to_existing_tenant(client, db_session: Session):
    from app.models.tenant import Tenant, TenantUser

    _seed_roles_and_level(db_session)

    admin = _create_verified_user(db_session, email="admin2@example.com", password="StrongPass1!", role_tipo="admin")
    owner = _create_verified_user(db_session, email="owner2@example.com", password="StrongPass1!", role_tipo="socio")
    member = _create_verified_user(db_session, email="member@example.com", password="StrongPass1!", role_tipo="usuario")

    tenant = Tenant(nombre="Tenant X", slug="tenant-x", creado_por=admin.id)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    db_session.add(TenantUser(tenant_id=tenant.id, user_id=owner.id, rol="owner"))
    db_session.commit()

    login = client.post("/api/v1/auth/login-json", json={"email": admin.email, "password": "StrongPass1!"})
    assert login.status_code == 200
    token = login.json()["access_token"]

    resp = client.post(
        f"/api/v1/tenants/admin/{tenant.id}/members",
        json={"user_email": member.email, "rol": "member"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204, resp.text

    login_member = client.post("/api/v1/auth/login-json", json={"email": member.email, "password": "StrongPass1!"})
    assert login_member.status_code == 200
    token_member = login_member.json()["access_token"]

    my_tenants = client.get("/api/v1/tenants/me", headers={"Authorization": f"Bearer {token_member}"})
    assert my_tenants.status_code == 200
    assert any(t["slug"] == "tenant-x" for t in my_tenants.json())

