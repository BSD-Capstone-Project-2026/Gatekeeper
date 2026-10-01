import pytest
from models import db, Door, Incident, AccessLog


@pytest.fixture
def unit_door(app):
    door = Door(name="Unit 40A Door", location="Floor 40", door_type="unit", associated_unit="40A", is_active=True)
    db.session.add(door)
    db.session.commit()
    return door


@pytest.fixture
def attempt(request_door, unit_door):
    return lambda user: request_door(user, unit_door)


@pytest.fixture
def people(make_user):
    return make_user(unit_number="40A"), make_user(unit_number="12B")


def run(attempt, people, pattern):
    resident, stranger = people
    for step in pattern:
        attempt(resident if step == "S" else stranger)


def test_success_resets_failure_count(attempt, people):
    run(attempt, people, "FFSF")
    assert Incident.query.count() == 0


def test_incident_only_after_three_failures_without_success(attempt, people):
    run(attempt, people, "FFSFF")
    assert Incident.query.count() == 0
    run(attempt, people, "F")
    assert Incident.query.count() == 1


def test_incident_window_matches_counted_failures(attempt, people, make_user, login, client):
    run(attempt, people, "FFSFFF")
    incident = Incident.query.one()
    failures = AccessLog.query.filter_by(success=False).order_by(AccessLog.timestamp).all()[2:]
    assert incident.first_attempt_time == failures[0].timestamp
    assert incident.attempt_count == 3
    login(make_user("management"))
    events = client.get(f"/api/incidents/{incident.id}").json["events"]
    assert len(events) == 3 and all(not e["success"] for e in events)


def test_further_failures_update_open_incident(attempt, people):
    run(attempt, people, "FFFF")
    incident = Incident.query.one()
    assert incident.attempt_count == 4
    assert incident.last_attempt_time == AccessLog.query.order_by(AccessLog.timestamp.desc()).first().timestamp
