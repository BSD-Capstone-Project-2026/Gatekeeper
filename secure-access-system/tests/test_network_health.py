from unittest.mock import patch, MagicMock
import pytest


@pytest.fixture
def network_host(app):
    app.config["NETWORK_CHECK_HOST"] = "gateway.building.local"
    yield
    app.config["NETWORK_CHECK_HOST"] = None


def test_network_unknown_when_not_configured(client):
    data = client.get("/health").json
    assert data["network"] == "unknown" and data["status"] == "healthy"


def test_network_healthy_when_probe_connects(client, network_host):
    with patch("routes.web.socket.create_connection", return_value=MagicMock()) as probe:
        data = client.get("/health").json
    assert data["network"] == "healthy" and data["status"] == "healthy"
    probe.assert_called_once_with(("gateway.building.local", 80), timeout=1)


def test_network_unhealthy_marks_degraded(client, network_host):
    with patch("routes.web.socket.create_connection", side_effect=OSError("unreachable")):
        data = client.get("/health").json
    assert data["network"] == "unhealthy" and data["status"] == "degraded"


def test_database_failure_marks_down(client):
    with patch("routes.web.db.session.execute", side_effect=Exception("db gone")):
        data = client.get("/health").json
    assert data["database"] == "unhealthy" and data["status"] == "down"


def test_dashboard_maps_states_to_colours(make_user, login, client):
    login(make_user("management"))
    page = client.get("/dashboard").data
    assert b"healthy: 'badge bg-success'" in page and b"unknown: 'badge bg-warning'" in page and b"unhealthy: 'badge bg-danger'" in page
