import pytest
from app import create_app
from config import TestConfig
from models import db, User, Door
from routes.web import rate_limiter


@pytest.fixture
def app():
    rate_limiter.attempts.clear()
    app = create_app(TestConfig)
    with app.app_context():
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def make_user(app):
    def _make(role="resident", email=None, password="Passw0rd!", **fields):
        email = email or f"{role}{User.query.count()}@test.local"
        user = User(first_name=role, last_name="test", username=email, email=email, role=role, **fields)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user
    return _make


@pytest.fixture
def login(client):
    def _login(user, password="Passw0rd!"):
        return client.post("/login", data={"email": user.email, "password": password})
    return _login


@pytest.fixture
def main_door(app):
    door = Door(name="Main Entrance", location="Lobby", door_type="main", is_active=True)
    db.session.add(door)
    db.session.commit()
    return door
