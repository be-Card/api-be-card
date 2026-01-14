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


def test_register_requires_email_verification_to_login(client, db_session: Session):
    _seed_minimal_auth_data(db_session)

    password = "StrongPass1!"
    register = client.post(
        "/api/v1/auth/register",
        json={
            "nombre_usuario": "newuser",
            "email": "newuser@example.com",
            "password": password,
            "nombres": "New",
            "apellidos": "User",
            "sexo": "M",
            "fecha_nac": date(1990, 1, 1).isoformat(),
            "telefono": None,
        },
    )
    assert register.status_code == 201
    reg_data = register.json()
    assert reg_data["message"]
    assert reg_data["user"]["email"] == "newuser@example.com"
    assert reg_data["user"]["verificado"] is False
    assert isinstance(reg_data.get("verification_link"), str) and "token=" in reg_data["verification_link"]

    login_before = client.post("/api/v1/auth/login-json", json={"email": "newuser@example.com", "password": password})
    assert login_before.status_code == 403

    token = reg_data["verification_link"].split("token=", 1)[1]
    verify = client.post("/api/v1/auth/verify-email", json={"token": token})
    assert verify.status_code == 200

    login_after = client.post("/api/v1/auth/login-json", json={"email": "newuser@example.com", "password": password})
    assert login_after.status_code == 200


def test_register_accepts_fecha_nacimiento_and_sexo_labels(client, db_session: Session):
    _seed_minimal_auth_data(db_session)

    password = "StrongPass1!"
    register = client.post(
        "/api/v1/auth/register",
        json={
            "nombre_usuario": "mlgarcia",
            "email": "matiasgarcia444@gmail.com",
            "password": password,
            "nombres": "Matias Luciano",
            "apellidos": "Garcia",
            "sexo": "MASCULINO",
            "fecha_nacimiento": "1994-11-24T00:00:00.000Z",
            "telefono": "+543625293513",
        },
    )
    assert register.status_code == 201
    data = register.json()
    assert data["user"]["sexo"] == "M"


def test_register_invalid_sexo_returns_422(client, db_session: Session):
    _seed_minimal_auth_data(db_session)

    register = client.post(
        "/api/v1/auth/register",
        json={
            "nombre_usuario": "badsexo",
            "email": "badsexo@example.com",
            "password": "StrongPass1!",
            "nombres": "Bad",
            "apellidos": "Sexo",
            "sexo": "OTRO",
            "fecha_nac": date(1990, 1, 1).isoformat(),
        },
    )
    assert register.status_code == 422

