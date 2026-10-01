import pytest
from models import db, Door, Incident, add_missing_columns


@pytest.fixture
def incident(app):
    door = Door(name="Unit 1A Door", door_type="unit", associated_unit="1A")
    db.session.add(door)
    db.session.flush()
    inc = Incident(unit_number="1A", door_id=door.id, incident_type="repeated_failed_attempts", status="open", attempt_count=3)
    db.session.add(inc)
    db.session.commit()
    return inc


@pytest.mark.parametrize("role", ["concierge", "management"])
def test_staff_acknowledges_open_incident(make_user, login, client, incident, role):
    staff = make_user(role)
    login(staff)
    assert client.post(f"/incidents/{incident.id}/acknowledge").status_code == 302
    db.session.refresh(incident)
    assert incident.status == "acknowledged"
    assert incident.acknowledged_by == staff.id and incident.acknowledged_at is not None


def test_resident_cannot_acknowledge(make_user, login, client, incident):
    login(make_user())
    assert client.post(f"/incidents/{incident.id}/acknowledge").status_code == 403
    assert incident.status == "open"


def test_acknowledged_not_counted_as_new(make_user, login, client, incident):
    login(make_user("concierge"))
    assert b"1 new" in client.get("/incident-list").data
    client.post(f"/incidents/{incident.id}/acknowledge")
    page = client.get("/incident-list").data
    assert b"0 new" in page and b"Acknowledged" in page and b">Acknowledge</button>" not in page


def test_existing_database_gets_new_columns(app):
    db.session.execute(db.text("ALTER TABLE incidents DROP COLUMN acknowledged_at"))
    db.session.commit()
    add_missing_columns()
    assert "acknowledged_at" in {c["name"] for c in db.inspect(db.engine).get_columns("incidents")}
