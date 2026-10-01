import importlib
import pytest
import config
from sqlalchemy import text
from app import create_app
from models import db, User
from scripts.encrypt_door_codes import encrypt_existing


def raw_code(user):
    return db.session.execute(text("SELECT door_code FROM users WHERE id = :id"), {"id": user.id}).scalar()


def test_door_code_stored_as_ciphertext(make_user):
    user = make_user(door_code="A1B2C3D4E5F60718")
    assert raw_code(user) != "A1B2C3D4E5F60718"
    assert "A1B2C3D4E5F60718" not in raw_code(user)


def test_door_code_round_trip(make_user):
    user = make_user(door_code="A1B2C3D4E5F60718")
    db.session.expire_all()
    assert user.door_code == "A1B2C3D4E5F60718"


def test_creation_page_shows_decrypted_code(make_user, login, client):
    login(make_user("management"))
    res = client.post("/create-user", data={"first_name": "Ann", "last_name": "Lee", "email": "ann@test.local", "role": "resident", "unit_number": "5C"})
    user = User.query.filter_by(email="ann@test.local").one()
    assert user.door_code.encode() in res.data
    assert raw_code(user).encode() not in res.data


def test_existing_plaintext_codes_are_encrypted(make_user):
    user = make_user()
    db.session.execute(text("UPDATE users SET door_code = 'PLAINCODE1234567' WHERE id = :id"), {"id": user.id})
    db.session.commit()
    db.session.expire_all()
    assert encrypt_existing() == 1
    assert raw_code(user) != "PLAINCODE1234567"
    assert user.door_code == "PLAINCODE1234567"
    assert encrypt_existing() == 0


def test_production_requires_encryption_key(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    try:
        with pytest.raises(RuntimeError, match="ENCRYPTION_KEY"):
            create_app(importlib.reload(config).Config)
    finally:
        monkeypatch.undo()
        importlib.reload(config)
