from datetime import date

from sqlmodel import Session


def _seed_roles_and_level(session: Session) -> None:
    from app.models.user_extended import TipoRolUsuario, TipoNivelUsuario

    if session.get(TipoRolUsuario, 1) is None:
        session.add(TipoRolUsuario(id=1, tipo="usuario", descripcion="Usuario básico"))
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


def test_admin_list_users_and_toggle_active(client, db_session: Session):
    from app.models.tenant import Tenant, TenantUser

    _seed_roles_and_level(db_session)
    admin = _create_verified_user(db_session, email="admin3@example.com", password="StrongPass1!", role_tipo="admin")
    user = _create_verified_user(db_session, email="u1@example.com", password="StrongPass1!", role_tipo="usuario")

    tenant = Tenant(nombre="T1", slug="t1", creado_por=admin.id, activo=True)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    db_session.add(TenantUser(tenant_id=tenant.id, user_id=user.id, rol="member"))
    db_session.commit()

    login = client.post("/api/v1/auth/login-json", json={"email": admin.email, "password": "StrongPass1!"})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = client.get("/api/v1/admin/users", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 2
    row = next(r for r in body["users"] if r["email"] == "u1@example.com")
    assert any(t["slug"] == "t1" for t in row["tenants"])

    resp2 = client.patch(f"/api/v1/admin/users/{user.id}/active", json={"activo": False}, headers=headers)
    assert resp2.status_code == 204

    resp3 = client.get("/api/v1/admin/users", params={"activo": False}, headers=headers)
    assert resp3.status_code == 200
    assert any(r["email"] == "u1@example.com" and r["activo"] is False for r in resp3.json()["users"])


def test_admin_list_tenants_and_toggle_active(client, db_session: Session):
    from app.models.tenant import Tenant

    _seed_roles_and_level(db_session)
    admin = _create_verified_user(db_session, email="admin4@example.com", password="StrongPass1!", role_tipo="admin")

    tenant = Tenant(nombre="Humulus", slug="humulus", creado_por=admin.id, activo=True)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    login = client.post("/api/v1/auth/login-json", json={"email": admin.email, "password": "StrongPass1!"})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = client.get("/api/v1/admin/tenants", headers=headers)
    assert resp.status_code == 200
    assert any(t["slug"] == "humulus" for t in resp.json()["tenants"])

    resp2 = client.patch(f"/api/v1/admin/tenants/{tenant.id}/active", json={"activo": False}, headers=headers)
    assert resp2.status_code == 204

    resp3 = client.get("/api/v1/admin/tenants", params={"activo": False}, headers=headers)
    assert resp3.status_code == 200
    assert any(t["slug"] == "humulus" and t["activo"] is False for t in resp3.json()["tenants"])

