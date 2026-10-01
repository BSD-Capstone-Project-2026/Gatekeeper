from datetime import datetime, timedelta
import pytest
from models import db, Door, AccessLog


@pytest.fixture
def door(app):
    door = Door(name="Lobby Door", door_type="main")
    db.session.add(door)
    db.session.commit()
    return door


def add_log(user, door, minutes_ago, success):
    db.session.add(AccessLog(user_id=user.id, door_id=door.id, success=success, failure_reason="" if success else "wifi mismatch",
                             timestamp=datetime.utcnow() - timedelta(minutes=minutes_ago)))
    db.session.commit()


def test_concierge_redirected_to_live_dashboard(make_user, login, client):
    res = login(make_user("concierge"))
    assert res.location.endswith("/concierge")
    assert b"Real-Time Door Activity" in client.get("/concierge").data


def test_management_still_lands_on_dashboard(make_user, login):
    assert login(make_user("management")).location.endswith("/dashboard")


def test_recent_logs_returns_newest_first(make_user, login, client, door):
    user = make_user()
    add_log(user, door, 10, True)
    add_log(user, door, 1, False)
    login(make_user("concierge"))
    data = client.get("/api/recent-logs").json
    assert [log["success"] for log in data["logs"]] == [False, True]
    assert data["logs"][0]["door_name"] == "Lobby Door" and data["logs"][0]["failure_reason"] == "wifi mismatch"
    assert data["cursor"] == data["logs"][0]["timestamp"]


def test_since_returns_only_newer_logs(make_user, login, client, door):
    user = make_user()
    add_log(user, door, 10, True)
    login(make_user("concierge"))
    cursor = client.get("/api/recent-logs").json["cursor"]
    assert client.get(f"/api/recent-logs?since={cursor}").json["logs"] == []
    add_log(user, door, 0, False)
    newer = client.get(f"/api/recent-logs?since={cursor}").json
    assert len(newer["logs"]) == 1 and newer["cursor"] != cursor


def test_invalid_since_rejected(make_user, login, client):
    login(make_user("concierge"))
    assert client.get("/api/recent-logs?since=yesterday").status_code == 400


@pytest.mark.parametrize("path", ["/concierge", "/api/recent-logs"])
def test_resident_denied(make_user, login, client, path):
    login(make_user())
    assert client.get(path).status_code == 403
