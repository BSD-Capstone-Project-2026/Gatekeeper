from datetime import datetime, timedelta
import pytest
from models import db, AccessLog, EntryRequest


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
