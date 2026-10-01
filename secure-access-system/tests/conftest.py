import pytest
from flask_jwt_extended import create_access_token
from app import create_app
from config import TestConfig
from models import db, User, Door
from utils.proximity import issue_proximity_token


@pytest.fixture
def app():
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
def request_door(client):
    def _request(user, door, near=True, **kwargs):
        token = create_access_token(identity=str(user.id), additional_claims={"role": user.role})
        payload = {"door_id": door.id, "proximity_token": issue_proximity_token(door.id) if near else None}
        return client.post("/api/access/request", json=payload, headers={"Authorization": f"Bearer {token}"}, **kwargs)
    return _request


@pytest.fixture
def main_door(app):
    door = Door(name="Main Entrance", location="Lobby", door_type="main", is_active=True)
    db.session.add(door)
    db.session.commit()
    return door
