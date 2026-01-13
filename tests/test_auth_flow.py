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


def test_login_me_refresh_rotation(client, db_session: Session):
    _seed_minimal_auth_data(db_session)
    password = "StrongPass1!"
    user = _create_user(db_session, email="test@example.com", password=password)

    login = client.post("/api/v1/auth/login-json", json={"email": user.email, "password": password})
    assert login.status_code == 200
    login_data = login.json()
    assert login_data["token_type"] == "bearer"
    assert isinstance(login_data["access_token"], str) and login_data["access_token"]
    assert isinstance(login_data["refresh_token"], str) and login_data["refresh_token"]

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {login_data['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == user.email

    refresh = client.post("/api/v1/auth/refresh", json={"refresh_token": login_data["refresh_token"]})
    assert refresh.status_code == 200
    refresh_data = refresh.json()
    assert isinstance(refresh_data["access_token"], str) and refresh_data["access_token"]
    assert isinstance(refresh_data["refresh_token"], str) and refresh_data["refresh_token"]
    assert refresh_data["refresh_token"] != login_data["refresh_token"]

    reused = client.post("/api/v1/auth/refresh", json={"refresh_token": login_data["refresh_token"]})
    assert reused.status_code == 401


def test_login_invalid_password_returns_401(client, db_session: Session):
    _seed_minimal_auth_data(db_session)
    _create_user(db_session, email="user2@example.com", password="StrongPass1!")

    login = client.post("/api/v1/auth/login-json", json={"email": "user2@example.com", "password": "wrong"})
    assert login.status_code == 401
