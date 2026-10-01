from datetime import datetime
import pytest
from models import db, Incident


@pytest.fixture
def incidents(app, make_user, login):
    login(make_user("management"))
    for unit, day, status in [("1A", 1, "open"), ("2B", 10, "open"), ("3C", 20, "acknowledged")]:
        db.session.add(Incident(unit_number=unit, status=status, attempt_count=3, trigger_rule="3 failed attempts within 10 minutes",
                                created_at=datetime(2026, 10, day, 9)))
    db.session.commit()


def units(client, query):
    page = client.get(f"/incident-list?{query}").data
    return [u for u in ("1A", "2B", "3C") if f"<td>{u}</td>".encode() in page], page


def test_date_range_limits_incidents(client, incidents):
    assert units(client, "start_date=2026-10-05&end_date=2026-10-15")[0] == ["2B"]


def test_single_bound_filters(client, incidents):
    assert units(client, "start_date=2026-10-10")[0] == ["2B", "3C"]
    assert units(client, "end_date=2026-10-10")[0] == ["1A", "2B"]


def test_filters_persist_in_form(client, incidents):
    page = units(client, "start_date=2026-10-05&end_date=2026-10-15")[1]
    assert b'value="2026-10-05"' in page and b'value="2026-10-15"' in page


def test_invalid_date_shows_error_and_is_ignored(client, incidents):
    shown, page = units(client, "start_date=nope")
    assert b"Invalid start date" in page and shown == ["1A", "2B", "3C"]


def test_new_count_reflects_filtered_incidents(client, incidents):
    assert b"1 new" in units(client, "start_date=2026-10-05")[1]
    assert b"2 new" in units(client, "")[1]
