from sqlmodel import Session


def _seed_minimal_auth_data(session: Session) -> None:
    from app.models.user_extended import TipoRolUsuario, TipoNivelUsuario

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


def _create_socio_with_tenant(session: Session):
    from datetime import date

    from app.models.tenant import Tenant, TenantUser
    from app.models.user_extended import UsuarioRol
    from app.services.users import UserService

    socio = UserService.create_user(
        session=session,
        nombre_usuario="socio1",
        email="socio1@example.com",
        password="StrongPass1!",
        nombre="Socio",
        apellido="Uno",
        sexo="M",
        fecha_nacimiento=date(1990, 1, 1),
        telefono=None,
    )
    socio.verificado = True
    session.add(socio)
    session.commit()
    session.refresh(socio)

    session.add(UsuarioRol(id_usuario=socio.id, id_rol=2))
    session.commit()

    tenant = Tenant(nombre="Tenant Test", slug="tenant-test", creado_por=socio.id)
    session.add(tenant)
    session.commit()
    session.refresh(tenant)

    session.add(TenantUser(tenant_id=tenant.id, user_id=socio.id, rol="owner"))
    session.commit()

    return socio, tenant


def test_create_client_happy_path(client, db_session: Session):
    _seed_minimal_auth_data(db_session)
    socio, tenant = _create_socio_with_tenant(db_session)

    login = client.post("/api/v1/auth/login-json", json={"email": socio.email, "password": "StrongPass1!"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-Slug": tenant.slug}

    payload = {
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "phone": "123",
        "address": "Calle 123",
        "gender": "Femenino",
        "birthDate": "1990-01-01",
    }
    created = client.post("/api/v1/clients/", json=payload, headers=headers)
    assert created.status_code == 201
    body = created.json()
    assert body["client"]["email"] == "ada@example.com"
    assert body["client"]["name"] == "Ada Lovelace"

    listed = client.get("/api/v1/clients/", params={"page": 1, "limit": 20}, headers=headers)
    assert listed.status_code == 200
    list_body = listed.json()
    assert any(c["email"] == "ada@example.com" for c in list_body["clients"])


def test_create_client_invalid_email_returns_422(client, db_session: Session):
    _seed_minimal_auth_data(db_session)
    socio, tenant = _create_socio_with_tenant(db_session)

    login = client.post("/api/v1/auth/login-json", json={"email": socio.email, "password": "StrongPass1!"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-Slug": tenant.slug}

    payload = {
        "name": "Bad Email",
        "email": "not-an-email",
        "gender": "Masculino",
        "birthDate": "1990-01-01",
    }
    created = client.post("/api/v1/clients/", json=payload, headers=headers)
    assert created.status_code == 422

