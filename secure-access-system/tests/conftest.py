import pytest
from flask_jwt_extended import create_access_token
from app import create_app
from config import TestConfig
from models import db, User, Door
from utils.proximity import issue_proximity_token


GROUPS = {
    "security": {"test_baseline", "test_emergency_override", "test_encryption", "test_log_integrity", "test_password_reset", "test_rate_limit",
                 "test_rbac", "test_revocation", "test_secrets", "test_server_validation", "test_session_timeout", "test_transactions"},
    "access": {"test_acknowledge", "test_backup_retention", "test_door_controls", "test_guest_cleaner_roles", "test_incident_detection",
               "test_incident_filter", "test_live_activity", "test_log_filters", "test_network_health", "test_notifications", "test_offline_indicator"},
    "visitors": {"test_lobby_requests", "test_parking_permits", "test_visitor_passes", "test_watchlist"},
    "desk": {"test_key_register", "test_lost_found", "test_packages", "test_shift_log"},
    "services": {"test_amenities", "test_announcements", "test_maintenance"}
}


def pytest_collection_modifyitems(items):
    for item in items:
        for group, files in GROUPS.items():
            if item.path.stem in files:
                item.add_marker(group)


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
