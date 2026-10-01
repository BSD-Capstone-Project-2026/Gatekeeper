from datetime import datetime, timedelta
import pytest
from models import db, AccessLog, AuditLog, EntryRequest, VisitorPass


@pytest.fixture
def unit_2a(make_user):
    return make_user(unit_number="2A")


def ask(client, name="Jordan Blake", unit="2A"):
    return client.post("/lobby/requests", data={"visitor_name": name, "unit": unit})


def status(client, entry):
    return client.get(f"/lobby/requests/{entry.token}/status").json["status"]


def test_kiosk_is_public_and_lists_units(client, unit_2a):
    page = client.get("/lobby").data.decode()
    assert "Request Entry" in page and '<option value="2A">' in page


def test_resident_receives_request_for_their_unit(client, unit_2a, make_user, login):
    assert ask(client).status_code == 302
    login(unit_2a)
    page = client.get("/visitors/lobby").data.decode()
    assert "Jordan Blake" in page and "Approve" in page and 'class="nav-badge">1<' in page
    login(make_user(unit_number="2B"))
    assert "Jordan Blake" not in client.get("/visitors/lobby").data.decode().split("Recent")[0]


def test_approve_opens_main_entrance_and_logs(client, unit_2a, login, main_door):
    ask(client)
    entry = EntryRequest.query.one()
    login(unit_2a)
    client.post(f"/visitors/lobby/{entry.id}/approve")
    assert status(client, entry) == "approved"
    log = AccessLog.query.one()
    assert (log.user_id, log.door_id, log.visitor_name, log.success) == (unit_2a.id, main_door.id, "Jordan Blake", True)


def test_deny_shows_not_approved(client, unit_2a, login):
    ask(client)
    entry = EntryRequest.query.one()
    login(unit_2a)
    client.post(f"/visitors/lobby/{entry.id}/deny")
    assert status(client, entry) == "denied"
    assert AccessLog.query.count() == 0
    assert b"Entry not approved" in client.get(f"/lobby/requests/{entry.token}").data


def test_request_expires_after_two_minutes(client, unit_2a, login):
    ask(client)
    entry = EntryRequest.query.one()
    assert 110 <= entry.seconds_left <= 120
    entry.expires_at = datetime.utcnow() - timedelta(seconds=1)
    db.session.commit()
    assert status(client, entry) == "expired"
    login(unit_2a)
    client.post(f"/visitors/lobby/{entry.id}/approve")
    assert status(client, entry) == "expired" and AccessLog.query.count() == 0


def test_concierge_sees_all_pending_with_time_left(client, unit_2a, make_user, login):
    make_user(unit_number="3B")
    ask(client, "Jordan Blake", "2A")
    ask(client, "Casey Wu", "3B")
    login(make_user("concierge"))
    page = client.get("/visitors/lobby").data.decode()
    assert "Jordan Blake" in page and "Casey Wu" in page and "unit 3B" in page and 'class="countdown"' in page
    assert "Approve</button>" not in page


def test_other_unit_cannot_decide_and_bad_unit_rejected(client, unit_2a, make_user, login):
    ask(client)
    entry = EntryRequest.query.one()
    login(make_user(unit_number="2B"))
    assert client.post(f"/visitors/lobby/{entry.id}/approve").status_code == 404
    assert ask(client, unit="99Z").status_code == 400


def checked_in(resident, minutes_left=60, code="TESTCODE"):
    now = datetime.utcnow()
    visitor_pass = VisitorPass(code=code, resident_id=resident.id, visitor_name="Sam Lee", valid_from=now - timedelta(minutes=5),
                               valid_until=now + timedelta(minutes=minutes_left), checked_in_at=now)
    db.session.add(visitor_pass)
    db.session.commit()
    return visitor_pass


def test_controls_locked_without_checked_in_pass(client, unit_2a, login):
    login(unit_2a)
    page = client.get("/visitors/lobby").data.decode()
    assert "Available while one of your visitors is checked in" in page and "Open Lobby Screen" not in page
    checked_in(unit_2a).checked_in_at = None
    db.session.commit()
    assert "These unlock once the front desk checks Sam Lee in" in client.get("/visitors/lobby").data.decode()
    assert client.post("/visitors/lobby/door").status_code == 403
    assert client.post("/visitors/lobby/elevator").status_code == 403


def test_host_opens_lobby_door_and_sends_elevator(client, unit_2a, login, main_door):
    checked_in(unit_2a)
    login(unit_2a)
    assert "Lobby door opened" in client.post("/visitors/lobby/door", follow_redirects=True).data.decode()
    log = AccessLog.query.one()
    assert (log.user_id, log.door_id, log.visitor_name, log.success) == (unit_2a.id, main_door.id, "Sam Lee", True)
    assert "Elevator on its way" in client.post("/visitors/lobby/elevator", follow_redirects=True).data.decode()
    assert AuditLog.query.filter_by(action="elevator_sent", user_id=unit_2a.id).count() == 1


def test_controls_end_when_pass_expires_or_is_revoked(client, unit_2a, make_user, login):
    visitor_pass = checked_in(unit_2a)
    login(make_user(unit_number="2B"))
    assert client.post("/visitors/lobby/door").status_code == 403
    login(unit_2a)
    visitor_pass.revoked_at = datetime.utcnow()
    db.session.commit()
    assert client.post("/visitors/lobby/door").status_code == 403
    checked_in(unit_2a, minutes_left=-1, code="OTHER")
    assert client.post("/visitors/lobby/elevator").status_code == 403


def test_controls_need_building_wifi(app, client, unit_2a, login):
    checked_in(unit_2a)
    login(unit_2a)
    app.config["BUILDING_NETWORKS"] = ["10.0.0.0/8"]
    assert "Connect to the building Wi-Fi" in client.get("/visitors/lobby").data.decode()
    assert client.post("/visitors/lobby/door").status_code == 403
    assert client.post("/visitors/lobby/elevator").status_code == 403
