import smtplib
from unittest.mock import patch
import pytest
from flask_jwt_extended import create_access_token
from models import db, Door, Notification
from utils.notifications import notify


@pytest.fixture
def mail(app):
    app.config["MAIL_SERVER"] = "smtp.test.local"
    with patch("utils.notifications.smtplib.SMTP") as smtp:
        yield smtp
    app.config["MAIL_SERVER"] = None


def trigger_incident(client, resident, stranger):
    door = Door(name="Unit 40A Door", door_type="unit", associated_unit="40A")
    db.session.add(door)
    db.session.commit()
    token = create_access_token(identity=str(stranger.id), additional_claims={"role": "resident"})
    for _ in range(3):
        client.post("/api/access/request", json={"door_id": door.id, "wifi_ssid": "Avengers-x", "proximity": True},
                    headers={"Authorization": f"Bearer {token}"})


def test_incident_creates_resident_notification(client, make_user):
    resident, stranger = make_user(unit_number="40A"), make_user(unit_number="12B")
    trigger_incident(client, resident, stranger)
    note = Notification.query.filter_by(user_id=resident.id).one()
    assert note.incident_id is not None and note.status == "queued"
    for field in ["repeated_failed_attempts", "3 failed attempts", "Unit 40A Door", "UTC"]:
        assert field in note.message


def test_email_sent_once_when_configured(client, make_user, mail):
    resident, stranger = make_user(unit_number="40A"), make_user(unit_number="12B")
    trigger_incident(client, resident, stranger)
    assert mail.return_value.__enter__.return_value.send_message.call_count == 1
    note = Notification.query.one()
    assert note.status == "sent" and note.sent_at is not None


def test_email_failure_recorded(app, make_user, mail):
    mail.side_effect = smtplib.SMTPException("down")
    assert notify(make_user(), "s", "m").status == "failed"


def test_profile_shows_unread_then_marks_read(make_user, login, client):
    user = make_user()
    notify(user, "s", "Alert one")
    login(user)
    first = client.get("/profile").data
    assert b"1 unread" in first and b"Alert one" in first
    assert b"unread" not in client.get("/profile").data


def test_api_returns_only_own_notifications(make_user, login, client):
    me, other = make_user(), make_user()
    notify(me, "s", "mine")
    notify(other, "s", "theirs")
    login(me)
    assert [n["message"] for n in client.get("/api/notifications").json] == ["mine"]


def test_password_reset_link_emailed(client, make_user, mail):
    user = make_user()
    client.post("/forgot-password", data={"email": user.email})
    sent = mail.return_value.__enter__.return_value.send_message.call_args[0][0]
    assert sent["To"] == user.email and user.reset_token in sent.get_content()
