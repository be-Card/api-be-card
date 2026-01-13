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


def test_create_client_happy_path(client, db_session: Session):
    _seed_minimal_auth_data(db_session)

    payload = {
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "phone": "123",
        "address": "Calle 123",
        "gender": "Femenino",
        "birthDate": "1990-01-01",
    }
    created = client.post("/api/v1/clients/", json=payload)
    assert created.status_code == 201
    body = created.json()
    assert body["client"]["email"] == "ada@example.com"
    assert body["client"]["name"] == "Ada Lovelace"

    listed = client.get("/api/v1/clients/", params={"page": 1, "limit": 20})
    assert listed.status_code == 200
    list_body = listed.json()
    assert any(c["email"] == "ada@example.com" for c in list_body["clients"])


def test_create_client_invalid_email_returns_422(client, db_session: Session):
    _seed_minimal_auth_data(db_session)

    payload = {
        "name": "Bad Email",
        "email": "not-an-email",
        "gender": "Masculino",
        "birthDate": "1990-01-01",
    }
    created = client.post("/api/v1/clients/", json=payload)
    assert created.status_code == 422

