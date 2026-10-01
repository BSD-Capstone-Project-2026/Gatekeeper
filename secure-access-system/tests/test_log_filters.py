from datetime import datetime
import pytest
from models import db, Door, AccessLog


@pytest.fixture
def logs(app, make_user, login):
    login(make_user("management"))
    user = make_user()
    lobby = Door(name="Lobby Door", door_type="main")
    gym = Door(name="Gym Door", door_type="common")
    db.session.add_all([lobby, gym])
    db.session.flush()
    for door, day in [(lobby, 1), (lobby, 10), (gym, 10)]:
        db.session.add(AccessLog(user_id=user.id, door_id=door.id, timestamp=datetime(2026, 3, day, 12), success=False,
                                 wifi_verified=True, proximity_verified=True, failure_reason="zone restriction"))
    db.session.commit()
    return lobby, gym


def rows(client, query):
    page = client.get(f"/incidents?{query}").data
    return page.count(b"<td>Lobby Door</td>"), page.count(b"<td>Gym Door</td>")


def test_filter_by_door(client, logs):
    assert rows(client, f"door_id={logs[0].id}") == (2, 0)


def test_filter_by_date_range(client, logs):
    assert rows(client, "start_date=2026-03-05&end_date=2026-03-31") == (1, 1)


def test_filter_by_door_and_date(client, logs):
    assert rows(client, f"door_id={logs[1].id}&start_date=2026-03-05") == (0, 1)


def test_selected_door_persists(client, logs):
    assert f'value="{logs[1].id}" selected'.encode() in client.get(f"/incidents?door_id={logs[1].id}").data


def test_invalid_date_shows_error_and_is_ignored(client, logs):
    page = client.get("/incidents?start_date=bad-date").data
    assert b"Invalid start date" in page
    assert rows(client, "start_date=bad-date") == (2, 1)


def test_rows_do_not_link_to_incident_pages(client, logs):
    assert b"/incidents/" not in client.get("/incidents").data
