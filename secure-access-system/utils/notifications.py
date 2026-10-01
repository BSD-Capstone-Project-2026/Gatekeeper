import smtplib
from datetime import datetime
from email.message import EmailMessage
from flask import current_app
from models import db, Notification


def send_email(to, subject, body):
    cfg = current_app.config
    if not cfg.get("MAIL_SERVER"):
        current_app.logger.info("Email to %s not sent (MAIL_SERVER not set): %s", to, subject)
        return None
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = cfg["MAIL_SENDER"], to, subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=10) as smtp:
            if cfg["MAIL_USE_TLS"]:
                smtp.starttls()
            if cfg.get("MAIL_USERNAME"):
                smtp.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
            smtp.send_message(msg)
        return True
    except (smtplib.SMTPException, OSError) as exc:
        current_app.logger.warning("Email to %s failed: %s", to, exc)
        return False


def notify(user, subject, message, incident_id=None):
    notification = Notification(user_id=user.id, incident_id=incident_id, message=message, status="queued")
    sent = send_email(user.email, subject, message)
    if sent is not None:
        notification.status = "sent" if sent else "failed"
        notification.sent_at = datetime.utcnow() if sent else None
    db.session.add(notification)
    db.session.commit()
    return notification
