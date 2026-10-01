from datetime import datetime, timedelta
import pytest
from models import db, ShiftLogEntry


@pytest.fixture
def priya(make_user, login):
    make_user(unit_number="4B")
    user = make_user("concierge")
    login(user)
    return user


def add(client, body="Plumber for 4B at 9 am", category="Maintenance", unit="4B", handover=False):
    data = {"body": body, "category": category, "unit": unit}
    if handover:
        data["handover"] = "on"
    return client.post("/desk/shift-log", data=data)


def test_entry_saved_with_author_time_category_and_unit(client, priya):
    assert add(client).status_code == 302
    entry = ShiftLogEntry.query.one()
    assert (entry.author_id, entry.category, entry.unit_number, entry.is_handover) == (priya.id, "Maintenance", "4B", False)
    assert datetime.utcnow() - entry.created_at < timedelta(minutes=1)
    assert "Plumber for 4B" in client.get("/desk/shift-log").data.decode()


def test_invalid_entries_rejected(client, priya):
    assert add(client, category="Gossip").status_code == 400
    assert add(client, body="").status_code == 400
    assert add(client, unit="9Z").status_code == 400
    assert add(client, unit="").status_code == 302


def test_search_by_date_unit_staff_and_keyword(client, priya, make_user, login):
    add(client)
    add(client, body="Lobby lights flickering", category="Note", unit="")
    old = ShiftLogEntry.query.filter_by(category="Note").one()
    old.created_at = datetime.utcnow() - timedelta(days=3)
    db.session.commit()
    lucas = make_user("concierge")
    login(lucas)
    add(client, body="Courier left a box", category="Delivery", unit="")

    def shown(query):
        page = client.get(f"/desk/shift-log?{query}").data.decode()
        return [text for text in ("Plumber for 4B", "Lobby lights", "Courier left") if text in page]

    assert shown("unit=4b") == ["Plumber for 4B"]
    assert shown("q=lights") == ["Lobby lights"]
    assert shown(f"staff={lucas.id}") == ["Courier left"]
    assert shown(f"date={old.created_at:%Y-%m-%d}&tz_offset=0") == ["Lobby lights"]


def test_handover_shown_to_next_concierge_until_acknowledged(client, priya, make_user, login):
    add(client, handover=True)
    entry = ShiftLogEntry.query.one()
    assert "Handover from" not in client.get("/dashboard").data.decode()
    lucas = make_user("concierge")
    login(lucas)
    assert "Handover from concierge test" in client.get("/dashboard").data.decode()
    client.post(f"/desk/shift-log/{entry.id}/acknowledge")
    assert entry.acknowledged_by == lucas.id
    assert "Handover from" not in client.get("/dashboard").data.decode()
    assert "Handover acknowledged by concierge" in client.get("/desk/shift-log").data.decode()


def test_residents_denied(client, priya, make_user, login):
    add(client, handover=True)
    login(make_user(unit_number="2A"))
    assert client.get("/desk/shift-log").status_code == 403
    assert add(client).status_code == 403
    assert client.post(f"/desk/shift-log/{ShiftLogEntry.query.first().id}/acknowledge").status_code == 403
