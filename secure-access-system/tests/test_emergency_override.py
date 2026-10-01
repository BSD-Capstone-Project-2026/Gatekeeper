import pytest
from models import AuditLog


def override(client, door, reason="Fire alarm", password="Passw0rd!", confirm="yes"):
    return client.post("/emergency-override", data={"door_id": door.id, "reason": reason, "password": password, "confirm": confirm})


@pytest.fixture
def manager(make_user, login):
    user = make_user("management")
    login(user)
    return user


def test_valid_override_logged_with_structured_fields(client, manager, main_door):
    res = override(client, main_door)
    assert res.status_code == 200 and b"Emergency override executed" in res.data
    entry = AuditLog.query.filter_by(action="emergency_override").one()
    assert (entry.performed_by, entry.door_id, entry.reason) == (manager.id, main_door.id, "Fire alarm")
    assert entry.timestamp is not None


@pytest.mark.parametrize("password", ["", "wrong-password"])
def test_wrong_or_missing_password_refused_and_logged(client, manager, main_door, password):
    res = override(client, main_door, password=password)
    assert res.status_code == 403 and b"Override refused" in res.data
    assert AuditLog.query.filter_by(action="emergency_override").count() == 0
    denied = AuditLog.query.filter_by(action="override_denied").one()
    assert denied.door_id == main_door.id and denied.performed_by == manager.id


@pytest.mark.parametrize("reason", ["", "   "])
def test_empty_reason_rejected(client, manager, main_door, reason):
    res = override(client, main_door, reason=reason)
    assert res.status_code == 400 and b"reason is required" in res.data
    assert AuditLog.query.count() == 0


def test_unconfirmed_override_rejected(client, manager, main_door):
    assert override(client, main_door, confirm="").status_code == 400


@pytest.mark.parametrize("role", ["concierge", "resident"])
def test_non_management_forbidden(make_user, login, client, main_door, role):
    login(make_user(role))
    assert override(client, main_door).status_code == 403
    assert AuditLog.query.filter_by(action="emergency_override").count() == 0


def test_audit_view_filters_overrides(client, manager, main_door):
    override(client, main_door)
    override(client, main_door, password="wrong")
    page = client.get("/audit?action=emergency_override").data
    assert b"Fire alarm" in page and b"override_denied</td>" not in page
    assert b"override_denied</td>" in client.get("/audit").data
