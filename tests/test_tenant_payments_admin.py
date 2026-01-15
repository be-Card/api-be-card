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


def test_admin_can_register_payment_and_list_payments(client, db_session: Session):
    from app.models.tenant import Tenant

    _seed_roles_and_level(db_session)
    admin = _create_verified_user(db_session, email="admin-pay@example.com", password="StrongPass1!", role_tipo="admin")

    tenant = Tenant(
        nombre="T Pay",
        slug="t-pay",
        creado_por=admin.id,
        activo=False,
        suscripcion_plan="mensual",
        suscripcion_estado="suspendida",
        suscripcion_precio_centavos=10000,
        suscripcion_moneda="ARS",
        suscripcion_periodo_dias=30,
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    login = client.post("/api/v1/auth/login-json", json={"email": admin.email, "password": "StrongPass1!"})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    created = client.post(
        f"/api/v1/admin/tenants/{tenant.id}/payments",
        json={"amount_centavos": 10000, "currency": "ARS", "months": 1},
        headers=headers,
    )
    assert created.status_code == 201, created.text

    listed = client.get(f"/api/v1/admin/tenants/{tenant.id}/payments", headers=headers)
    assert listed.status_code == 200
    payments = listed.json()["payments"]
    assert len(payments) == 1
    assert payments[0]["amount_centavos"] == 10000

    db_session.expire_all()
    refreshed = db_session.get(Tenant, tenant.id)
    assert refreshed is not None
    assert refreshed.activo is True
    assert refreshed.suscripcion_estado == "activa"
    assert refreshed.suscripcion_hasta is not None
