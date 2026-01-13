from datetime import date
from sqlmodel import Session


def _seed_minimal_auth_data(session: Session) -> None:
    from app.models.user_extended import TipoRolUsuario, TipoNivelUsuario

    if session.get(TipoRolUsuario, 1) is None:
        session.add(TipoRolUsuario(id=1, tipo="usuario", descripcion="Usuario básico"))
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


def _create_user(session: Session, *, email: str, password: str):
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
    )
    user.verificado = True
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _login(client, email: str, password: str) -> str:
    res = client.post("/api/v1/auth/login-json", json={"email": email, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


def test_profile_me_get_and_update(client, db_session: Session):
    _seed_minimal_auth_data(db_session)
    password = "StrongPass1!"
    user = _create_user(db_session, email="profile@example.com", password=password)
    token = _login(client, user.email, password)
    headers = {"Authorization": f"Bearer {token}"}

    get1 = client.get("/api/v1/profile/me", headers=headers)
    assert get1.status_code == 200
    data1 = get1.json()
    assert data1["id"] == user.id
    assert data1["nombres"] == "Test"
    assert data1["apellidos"] == "User"
    assert "stats" in data1 and isinstance(data1["stats"]["sessions"], int)
    assert "professional" in data1

    update = client.put(
        "/api/v1/profile/me",
        headers=headers,
        json={
            "nombres": "Maria",
            "apellidos": "Salazar",
            "telefono": "+541112345678",
            "direccion": "Av. Corrientes 1234, CABA",
            "puesto": "Gerente General",
            "departamento": "Administración",
            "fecha_ingreso": "2024-01-15",
            "id_empleado": "EMP-001",
        },
    )
    assert update.status_code == 200
    data2 = update.json()
    assert data2["nombres"] == "Maria"
    assert data2["direccion"] == "Av. Corrientes 1234, CABA"
    assert data2["professional"]["puesto"] == "Gerente General"
    assert data2["professional"]["fecha_ingreso"] == "2024-01-15"

    get2 = client.get("/api/v1/profile/me", headers=headers)
    assert get2.status_code == 200
    data3 = get2.json()
    assert data3["nombres"] == "Maria"
    assert data3["professional"]["id_empleado"] == "EMP-001"


def test_profile_me_invalid_date_returns_400(client, db_session: Session):
    _seed_minimal_auth_data(db_session)
    password = "StrongPass1!"
    user = _create_user(db_session, email="profile2@example.com", password=password)
    token = _login(client, user.email, password)
    headers = {"Authorization": f"Bearer {token}"}

    res = client.put(
        "/api/v1/profile/me",
        headers=headers,
        json={
            "nombres": "Test",
            "apellidos": "User",
            "telefono": None,
            "direccion": None,
            "puesto": None,
            "departamento": None,
            "fecha_ingreso": "not-a-date",
            "id_empleado": None,
        },
    )
    assert res.status_code == 400
