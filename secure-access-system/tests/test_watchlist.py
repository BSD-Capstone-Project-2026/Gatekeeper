from datetime import datetime, timedelta
import pytest
from models import db, AccessLog, AuditLog, EntryRequest, VisitorPass, WatchlistEntry


@pytest.fixture
def manager(make_user, login):
    user = make_user("management")
    login(user)
    return user


def bar(client, name="Alex Stone", reason="Threatened staff"):
    return client.post("/visitors/watchlist", data={"name": name, "reason": reason})


def new_pass(client, name):
    now = datetime.utcnow()
    return client.post("/visitors/passes", data={"visitor_name": name, "valid_from": now.strftime("%Y-%m-%dT%H:%M"),
                                                 "valid_until": (now + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M"), "tz_offset": "0"})


def test_manager_adds_entry_with_reason_and_date(client, manager):
    assert bar(client).status_code == 302
    page = client.get("/visitors/watchlist").data.decode()
    assert "Alex Stone" in page and "Threatened staff" in page and "Added" in page


def test_pass_for_barred_name_refused(client, manager, make_user, login):
    bar(client)
    login(make_user(unit_number="2A"))
    res = new_pass(client, "  alex   STONE ")
    assert res.status_code == 400 and b"This visitor cannot be admitted" in res.data
    assert VisitorPass.query.count() == 0


def test_lobby_request_for_barred_name_refused(client, manager, make_user):
    bar(client)
    make_user(unit_number="2A")
    res = client.post("/lobby/requests", data={"visitor_name": "Alex Stone", "unit": "2A"})
    assert res.status_code == 403 and b"This visitor cannot be admitted" in res.data
    assert EntryRequest.query.count() == 0


def test_existing_pass_refused_once_barred(client, manager, make_user, login, main_door):
    resident = make_user(unit_number="2A")
    login(resident)
    new_pass(client, "Alex Stone")
    code = VisitorPass.query.one().code
    login(manager)
    bar(client)
    login(make_user("concierge"))
    assert b"This visitor cannot be admitted" in client.post("/visitors/passes/check", data={"code": code}).data
    assert AccessLog.query.one().success is False


def test_concierge_front_desk_shows_alert_with_name_and_unit(client, manager, make_user, login):
    bar(client)
    login(make_user(unit_number="3B"))
    new_pass(client, "Alex Stone")
    login(make_user("concierge"))
    page = client.get("/dashboard").data.decode()
    assert "Watchlisted visitor refused" in page and "Alex Stone · unit 3B" in page


def test_removal_allows_pass_and_is_audited(client, manager, make_user, login):
    bar(client)
    entry = WatchlistEntry.query.one()
    client.post(f"/visitors/watchlist/{entry.id}/remove")
    assert AuditLog.query.filter_by(action="watchlist_removed", details="Alex Stone").count() == 1
    login(make_user(unit_number="2A"))
    assert new_pass(client, "Alex Stone").status_code == 302


def test_only_management_edits(client, manager, make_user, login):
    bar(client)
    entry = WatchlistEntry.query.one()
    login(make_user("concierge"))
    page = client.get("/visitors/watchlist?q=alex").data.decode()
    assert "Alex Stone" in page and "Add to Watchlist" not in page
    assert bar(client, "Other Person").status_code == 403
    assert client.post(f"/visitors/watchlist/{entry.id}/remove").status_code == 403
    login(make_user())
    assert client.get("/visitors/watchlist").status_code == 403
