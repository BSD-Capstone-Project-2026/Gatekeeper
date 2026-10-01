from datetime import datetime, timedelta
import pytest
from models import db, Incident, Zone


@pytest.mark.parametrize("role, label, marker", [
    ("management", "Dashboard</a>", "Users by Role"),
    ("concierge", "Front Desk</a>", "Alerts to Handle"),
    ("resident", "Home</a>", "Building access"),
    ("cleaner", "Home</a>", "shared areas")])
def test_each_role_gets_its_own_home(make_user, login, client, role, label, marker):
    login(make_user(role))
    page = client.get("/dashboard").data.decode()
    assert label in page and marker in page


def test_front_desk_actions_return_to_front_desk(make_user, login, client, main_door):
    db.session.add(Incident(unit_number="2A", status="open", attempt_count=3))
    db.session.commit()
    login(make_user("concierge"))
    page = client.get("/dashboard").data.decode()
    assert "Unit 2A · 3 failed attempts" in page and "Main Entrance" in page and "System Health" in page
    incident = Incident.query.one()
    assert client.post(f"/incidents/{incident.id}/acknowledge", data={"next": "dashboard"}).location.endswith("/dashboard")
    assert client.post(f"/doors/{main_door.id}/unlock", data={"next": "dashboard"}).location.endswith("/dashboard")
    assert client.post(f"/doors/{main_door.id}/lock").location.endswith("/door-controls")


def test_resident_home_shows_areas_and_activity(make_user, login, client):
    zone = Zone(name="Gym", description="Fitness")
    db.session.add(zone)
    user = make_user(unit_number="3A", floor=3)
    user.zones.append(zone)
    db.session.commit()
    login(user)
    page = client.get("/dashboard").data.decode()
    assert "Hi, resident" in page and "Unit 3A · Floor 3" in page and ">Gym<" in page and "Open Access" in page


def test_guest_home_shows_validity(make_user, login, client):
    login(make_user("guest", access_expires_at=datetime.utcnow() + timedelta(days=3)))
    assert "Valid until" in client.get("/dashboard").data.decode()
