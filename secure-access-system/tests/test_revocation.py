import pytest
from flask_jwt_extended import create_access_token
from models import db, AccessLog


def token_for(user_id, role="resident"):
    return {"Authorization": f"Bearer {create_access_token(identity=str(user_id), additional_claims={'role': role})}"}


def unlock(client, headers, door):
    return client.post("/api/access/request", json={"door_id": door.id}, headers=headers)


@pytest.mark.parametrize("field, value, reason", [("is_active", False, "account inactive"), ("is_locked", True, "account locked")])
def test_revoked_account_refused_with_old_token(client, make_user, main_door, field, value, reason):
    user = make_user()
    headers = token_for(user.id)
    setattr(user, field, value)
    db.session.commit()
    res = unlock(client, headers, main_door)
    assert res.status_code == 403 and res.json["access_granted"] is False
    assert AccessLog.query.filter_by(user_id=user.id).one().failure_reason == reason


def test_unknown_user_returns_404(client, main_door):
    assert unlock(client, token_for(999), main_door).status_code == 404


@pytest.mark.parametrize("field, value", [("is_active", False), ("is_locked", True)])
def test_elevator_refuses_revoked_account(client, make_user, field, value):
    user = make_user(floor=4)
    headers = token_for(user.id)
    setattr(user, field, value)
    db.session.commit()
    assert client.post("/api/access/elevator/call", headers=headers).status_code == 403


def test_elevator_unknown_user_returns_404(client):
    assert client.post("/api/access/elevator/call", headers=token_for(999)).status_code == 404


def test_active_resident_can_call_elevator(client, make_user):
    user = make_user(floor=4)
    assert client.post("/api/access/elevator/call", headers=token_for(user.id)).json["floor"] == 4
