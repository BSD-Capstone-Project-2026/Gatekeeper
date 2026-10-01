import pytest
from models import AuditLog, User

STAFF_ONLY = ["/users", "/api/dashboard/stats", "/api/dashboard/recent-users", "/incident-list"]
MANAGEMENT_ONLY = ["/doors", "/zones", "/incidents", "/emergency-override"]


@pytest.mark.parametrize("path", STAFF_ONLY + MANAGEMENT_ONLY)
def test_resident_denied_and_logged(make_user, login, client, path):
    resident = make_user()
    login(resident)
    assert client.get(path).status_code == 403
    entry = AuditLog.query.filter_by(action="access_denied").one()
    assert entry.user_id == resident.id and path in entry.details


@pytest.mark.parametrize("path", MANAGEMENT_ONLY)
def test_concierge_denied_management_pages(make_user, login, client, path):
    login(make_user("concierge"))
    assert client.get(path).status_code == 403


@pytest.mark.parametrize("path", STAFF_ONLY)
def test_concierge_allowed_staff_pages(make_user, login, client, path):
    login(make_user("concierge"))
    assert client.get(path).status_code == 200


def test_concierge_sees_only_residents(make_user, login, client):
    make_user("management", email="boss@test.local")
    make_user(email="res@test.local")
    login(make_user("concierge"))
    page = client.get("/users").data
    assert b"res@test.local" in page and b"boss@test.local" not in page


def test_dashboard_hides_user_list_from_residents(make_user, login, client):
    make_user("management", email="boss@test.local")
    login(make_user())
    assert b"boss@test.local" not in client.get("/dashboard").data


@pytest.mark.parametrize("action, field, expected", [("/users/toggle", "is_active", False), ("/unlock-user", "is_locked", False)])
def test_state_changes_require_post(make_user, login, client, action, field, expected):
    target = make_user(email="target@test.local", is_locked=True)
    login(make_user("management"))
    assert client.get(f"{action}/{target.id}").status_code == 405
    assert client.post(f"{action}/{target.id}").status_code == 302
    assert getattr(User.query.get(target.id), field) is expected
