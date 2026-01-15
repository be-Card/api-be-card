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


def test_tenant_can_create_list_and_delete_own_styles(client, db_session: Session):
    from app.models.tenant import Tenant, TenantUser
    from app.models.beer import TipoEstiloCerveza

    _seed_roles_and_level(db_session)
    admin = _create_verified_user(db_session, email="admin-style@example.com", password="StrongPass1!", role_tipo="admin")

    tenant = Tenant(nombre="T Styles", slug="t-styles", creado_por=admin.id, activo=True)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    db_session.add(TenantUser(tenant_id=tenant.id, user_id=admin.id, rol="owner"))
    db_session.add(TipoEstiloCerveza(estilo="Global IPA", descripcion=None, origen=None, tenant_id=None))
    db_session.commit()

    login = client.post("/api/v1/auth/login-json", json={"email": admin.email, "password": "StrongPass1!"})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}", "X-Tenant-Slug": tenant.slug}

    created = client.post(
        "/api/v1/cervezas/estilos",
        json={"estilo": "Mi Estilo", "descripcion": "Desc", "origen": "AR"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    created_id = created.json()["id"]

    listed = client.get("/api/v1/cervezas/estilos", headers=headers)
    assert listed.status_code == 200
    styles = listed.json()
    assert any(s["estilo"] == "Global IPA" for s in styles)
    assert any(s["estilo"] == "Mi Estilo" for s in styles)

    deleted = client.delete(f"/api/v1/cervezas/estilos/{created_id}", headers=headers)
    assert deleted.status_code == 204, deleted.text


def test_cannot_delete_global_style(client, db_session: Session):
    from app.models.tenant import Tenant, TenantUser
    from app.models.beer import TipoEstiloCerveza

    _seed_roles_and_level(db_session)
    admin = _create_verified_user(db_session, email="admin-style2@example.com", password="StrongPass1!", role_tipo="admin")

    tenant = Tenant(nombre="T Styles 2", slug="t-styles-2", creado_por=admin.id, activo=True)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    db_session.add(TenantUser(tenant_id=tenant.id, user_id=admin.id, rol="owner"))
    global_style = TipoEstiloCerveza(estilo="Global Lager", descripcion=None, origen=None, tenant_id=None)
    db_session.add(global_style)
    db_session.commit()
    db_session.refresh(global_style)

    login = client.post("/api/v1/auth/login-json", json={"email": admin.email, "password": "StrongPass1!"})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}", "X-Tenant-Slug": tenant.slug}

    resp = client.delete(f"/api/v1/cervezas/estilos/{global_style.id}", headers=headers)
    assert resp.status_code == 400

