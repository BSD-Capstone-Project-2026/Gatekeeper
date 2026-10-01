import time
from unittest.mock import patch
import pytest


@pytest.fixture
def clock():
    now = [time.time()]
    with patch("routes.web.time.time", side_effect=lambda: now[0]):
        yield now


def advance(clock, minutes):
    clock[0] += minutes * 60


def test_idle_session_expires(make_user, login, client, clock):
    login(make_user("concierge"))
    advance(clock, 16)
    res = client.get("/users")
    assert res.status_code == 302 and "expired=1" in res.location
    assert b"Session expired" in client.get(res.location).data
    assert client.get("/users").location.endswith("/login")


def test_activity_resets_timer(make_user, login, client, clock):
    login(make_user("concierge"))
    for _ in range(3):
        advance(clock, 10)
        assert client.get("/users").status_code == 200


def test_background_polling_does_not_keep_session_alive(make_user, login, client, clock):
    login(make_user("concierge"))
    for _ in range(3):
        advance(clock, 5)
        client.get("/health")
    advance(clock, 1)
    assert client.get("/api/recent-logs").status_code == 401


def test_expired_session_token_cleared(make_user, login, client, clock):
    login(make_user())
    advance(clock, 16)
    client.get("/profile")
    with client.session_transaction() as sess:
        assert "jwt_token" not in sess and "user_id" not in sess


def test_timeout_is_configurable(app, make_user, login, client, clock):
    app.config["SESSION_TIMEOUT_MINUTES"] = 30
    login(make_user("concierge"))
    advance(clock, 20)
    assert client.get("/users").status_code == 200
