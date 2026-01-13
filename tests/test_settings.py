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


def test_preferences_persist_and_reload(client, db_session: Session):
    _seed_minimal_auth_data(db_session)
    password = "StrongPass1!"
    user = _create_user(db_session, email="settings@example.com", password=password)
    token = _login(client, user.email, password)
    headers = {"Authorization": f"Bearer {token}"}

    get1 = client.get("/api/v1/settings/preferences", headers=headers)
    assert get1.status_code == 200
    prefs1 = get1.json()["preferences"]
    assert prefs1["language"] == "es"
    assert prefs1["theme"] == "dark"

    update = client.put(
        "/api/v1/settings/preferences",
        headers=headers,
        json={
            **prefs1,
            "language": "en",
            "notifications_email_sales": False,
        },
    )
    assert update.status_code == 200
    prefs2 = update.json()["preferences"]
    assert prefs2["language"] == "en"
    assert prefs2["notifications_email_sales"] is False

    get2 = client.get("/api/v1/settings/preferences", headers=headers)
    assert get2.status_code == 200
    prefs3 = get2.json()["preferences"]
    assert prefs3["language"] == "en"
    assert prefs3["notifications_email_sales"] is False


def test_active_sessions_and_close_session(client, db_session: Session):
    _seed_minimal_auth_data(db_session)
    password = "StrongPass1!"
    user = _create_user(db_session, email="sessions@example.com", password=password)
    token = _login(client, user.email, password)
    headers = {"Authorization": f"Bearer {token}"}

    sessions = client.get("/api/v1/settings/active-sessions", headers=headers)
    assert sessions.status_code == 200
    data = sessions.json()
    assert data["total"] >= 1
    first = data["sessions"][0]
    assert isinstance(first["id"], str) and first["id"]

    close = client.delete(f"/api/v1/settings/sessions/{first['id']}", headers=headers)
    assert close.status_code == 200

    sessions2 = client.get("/api/v1/settings/active-sessions", headers=headers)
    assert sessions2.status_code == 200
    assert sessions2.json()["total"] == 0
