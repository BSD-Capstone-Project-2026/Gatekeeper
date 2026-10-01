from datetime import datetime, timedelta
import pytest
from flask_jwt_extended import create_access_token
from models import db, Door, User, AccessLog

TOMORROW = datetime.utcnow() + timedelta(days=1)


@pytest.fixture
def doors(app):
    doors = {t: Door(name=f"{t.title()} Door", door_type=t, associated_unit="4B" if t == "unit" else None) for t in ("main", "common", "unit")}
    db.session.add_all(doors.values())
    db.session.commit()
    return doors


def unlock(client, user, door):
    token = create_access_token(identity=str(user.id), additional_claims={"role": user.role})
    return client.post("/api/access/request", json={"door_id": door.id, "wifi_ssid": "Avengers-x", "proximity": True},
                       headers={"Authorization": f"Bearer {token}"})


def create(client, **form):
    return client.post("/create-user", data={"first_name": "Sam", "last_name": "Lee", "email": "sam@test.local", **form})


@pytest.mark.parametrize("creator, role, allowed", [
    ("management", "guest", True), ("management", "cleaner", True),
    ("concierge", "guest", True), ("concierge", "cleaner", False), ("concierge", "concierge", False)])
def test_who_can_create_which_role(make_user, login, client, creator, role, allowed):
    login(make_user(creator))
    create(client, role=role, access_expires_at=TOMORROW.strftime("%Y-%m-%d"))
    assert (User.query.filter_by(email="sam@test.local").first() is not None) is allowed


@pytest.mark.parametrize("date, error", [("", b"access end date"), ("2020-01-01", b"must be in the future")])
def test_guest_requires_future_end_date(make_user, login, client, date, error):
    login(make_user("management"))
    assert error in create(client, role="guest", access_expires_at=date).data
    assert User.query.filter_by(email="sam@test.local").first() is None


@pytest.mark.parametrize("role, main, common, unit", [("guest", 200, 403, 403), ("cleaner", 200, 200, 403)])
def test_door_rights_by_role(client, make_user, doors, role, main, common, unit):
    user = make_user(role, access_expires_at=TOMORROW)
    assert [unlock(client, user, doors[t]).status_code for t in ("main", "common", "unit")] == [main, common, unit]


def test_expired_guest_denied(client, make_user, doors):
    guest = make_user("guest", access_expires_at=datetime.utcnow() - timedelta(minutes=1))
    assert unlock(client, guest, doors["main"]).status_code == 403
    assert AccessLog.query.filter_by(user_id=guest.id).one().failure_reason == "guest access expired"


@pytest.mark.parametrize("role", ["guest", "cleaner"])
def test_guest_and_cleaner_pages(make_user, login, client, doors, role):
    login(make_user(role, access_expires_at=TOMORROW))
    page = client.get("/simulate").data.decode()
    assert page.count("access-tile") == 1 and "Call Elevator" not in page
    assert client.get("/users").status_code == 403


def test_concierge_sees_guests(make_user, login, client):
    make_user("guest", email="visitor@test.local", access_expires_at=TOMORROW)
    make_user("cleaner", email="cleaner@test.local")
    login(make_user("concierge"))
    page = client.get("/users").data
    assert b"visitor@test.local" in page and b"cleaner@test.local" not in page
