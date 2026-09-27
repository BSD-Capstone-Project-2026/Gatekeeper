from datetime import datetime, timedelta
from models import db


def request_token(client, user):
    client.post("/forgot-password", data={"email": user.email})
    return user.reset_token


def test_forgot_password_page_renders(client):
    assert client.get("/forgot-password").status_code == 200


def test_response_is_neutral(client, make_user):
    user = make_user()
    known = client.post("/forgot-password", data={"email": user.email}).data
    unknown = client.post("/forgot-password", data={"email": "nobody@test.local"}).data
    assert known == unknown
    assert user.reset_token.encode() not in known


def test_valid_token_resets_password(client, make_user):
    user = make_user()
    token = request_token(client, user)
    res = client.post(f"/reset-password/{token}", data={"new_password": "NewPass123", "confirm_password": "NewPass123"})
    assert res.status_code == 302 and "reset=1" in res.location
    assert user.check_password("NewPass123") and user.reset_token is None


def test_short_or_mismatched_password_rejected(client, make_user):
    user = make_user()
    token = request_token(client, user)
    assert b"at least 8" in client.post(f"/reset-password/{token}", data={"new_password": "short", "confirm_password": "short"}).data
    assert b"do not match" in client.post(f"/reset-password/{token}", data={"new_password": "NewPass123", "confirm_password": "Other1234"}).data


def test_expired_or_used_token_shows_invalid(client, make_user):
    user = make_user()
    token = request_token(client, user)
    user.reset_token_expiry = datetime.utcnow() - timedelta(minutes=1)
    db.session.commit()
    assert b"invalid or has expired" in client.get(f"/reset-password/{token}").data
    assert b"invalid or has expired" in client.get("/reset-password/used-token").data
