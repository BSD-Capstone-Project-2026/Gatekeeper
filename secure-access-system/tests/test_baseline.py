from flask_jwt_extended import create_access_token
from models import AccessLog


def test_health(client):
    assert client.get("/health").json["database"] == "healthy"


def test_login_success_redirects_to_dashboard(make_user, login):
    res = login(make_user("management"))
    assert res.status_code == 302 and res.location.endswith("/dashboard")


def test_account_locks_after_three_failures(make_user, login):
    user = make_user()
    for _ in range(3):
        login(user, "wrong")
    assert user.is_locked
    assert b"locked" in login(user).data


def test_resident_blocked_from_management_page(make_user, login, client):
    login(make_user())
    assert client.get("/doors").status_code == 403


def test_main_door_access_is_logged(app, client, make_user, main_door):
    user = make_user()
    token = create_access_token(identity=str(user.id), additional_claims={"role": user.role})
    res = client.post("/api/access/request", json={"door_id": main_door.id, "wifi_ssid": "Avengers-x", "proximity": True},
                      headers={"Authorization": f"Bearer {token}"})
    assert res.json["access_granted"] is True
    assert AccessLog.query.filter_by(user_id=user.id, success=True).count() == 1
