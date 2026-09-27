import importlib
import warnings
import config
from flask_jwt_extended import create_access_token
from models import User


def test_only_hash_is_stored(make_user):
    user = make_user(password="Secret123!")
    assert user.temporary_password is None
    assert "Secret123!" not in user.password_hash
    assert user.check_password("Secret123!")


def test_created_password_shown_once_not_stored(make_user, login, client):
    login(make_user("management"))
    res = client.post("/create-user", data={"first_name": "Ann", "last_name": "Lee", "email": "ann@test.local", "role": "concierge"})
    user = User.query.filter_by(email="ann@test.local").one()
    assert b"Temporary Password" in res.data
    assert user.temporary_password is None
    assert b"Temp Password" not in client.get("/users").data


def test_secrets_read_from_environment(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "s" * 64)
    monkeypatch.setenv("JWT_SECRET_KEY", "j" * 64)
    try:
        cfg = importlib.reload(config).Config
        assert cfg.SECRET_KEY == "s" * 64 and cfg.JWT_SECRET_KEY == "j" * 64
    finally:
        monkeypatch.undo()
        importlib.reload(config)


def test_jwt_key_has_no_length_warning(app):
    assert len(app.config["JWT_SECRET_KEY"]) >= 32
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        create_access_token(identity="1")
