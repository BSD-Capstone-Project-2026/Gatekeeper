import pytest
from flask_jwt_extended import create_access_token
from models import db, Door, AccessLog

OUTSIDE = {"environ_base": {"REMOTE_ADDR": "203.0.113.9"}}


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(identity=str(user.id), additional_claims={'role': user.role})}"}


def last_reason(user):
    return AccessLog.query.filter_by(user_id=user.id).order_by(AccessLog.id.desc()).first().failure_reason


def test_trusted_network_and_token_unlock(make_user, main_door, request_door):
    user = make_user()
    assert request_door(user, main_door).status_code == 200
    log = AccessLog.query.filter_by(user_id=user.id).one()
    assert log.wifi_verified is True and log.proximity_verified is True


def test_outside_network_denied_even_with_matching_ssid(client, make_user, main_door, request_door):
    user = make_user()
    assert request_door(user, main_door, **OUTSIDE).status_code == 403
    assert "network not trusted" in last_reason(user)
    res = client.post("/api/access/request", json={"door_id": main_door.id, "wifi_ssid": "Avengers-x", "proximity": True},
                      headers=auth(user), **OUTSIDE)
    assert res.status_code == 403


def test_missing_token_denied(make_user, main_door, request_door):
    user = make_user()
    assert request_door(user, main_door, near=False).status_code == 403
    assert last_reason(user) == "proximity not verified"


def test_expired_token_denied(app, make_user, main_door, request_door):
    app.config["PROXIMITY_TOKEN_SECONDS"] = -1
    user = make_user()
    assert request_door(user, main_door).status_code == 403
    assert last_reason(user) == "proximity not verified"


def test_token_for_another_door_denied(client, make_user, main_door):
    other = Door(name="Side Door", door_type="main")
    db.session.add(other)
    db.session.commit()
    user = make_user()
    token = client.get(f"/api/access/beacon/{other.id}", headers=auth(user)).json["proximity_token"]
    res = client.post("/api/access/request", json={"door_id": main_door.id, "proximity_token": token}, headers=auth(user))
    assert res.status_code == 403 and last_reason(user) == "proximity not verified"


def test_beacon_rules(client, make_user, main_door):
    user = make_user()
    data = client.get(f"/api/access/beacon/{main_door.id}", headers=auth(user)).json
    assert data["door_id"] == main_door.id and data["expires_in"] == 30 and data["proximity_token"]
    assert client.get(f"/api/access/beacon/{main_door.id}", headers=auth(user), **OUTSIDE).status_code == 403
    assert client.get("/api/access/beacon/999", headers=auth(user)).status_code == 404
    assert client.get(f"/api/access/beacon/{main_door.id}").status_code == 401
