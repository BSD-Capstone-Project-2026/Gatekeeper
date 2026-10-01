from datetime import datetime, timedelta
import pytest
from models import db, AccessLog, seal_existing_logs
from utils.log_integrity import verify_log_chain


@pytest.fixture
def logs(app):
    for i in range(4):
        db.session.add(AccessLog(user_id=1, door_id=1, success=i % 2 == 0, failure_reason="" if i % 2 == 0 else "wifi mismatch",
                                 timestamp=datetime.utcnow() - timedelta(minutes=10 - i)))
        db.session.commit()
    return AccessLog.query.order_by(AccessLog.id).all()


def raw(sql, **params):
    db.session.execute(db.text(sql), params)
    db.session.commit()
    db.session.expire_all()


def test_each_log_links_to_previous(logs):
    assert logs[0].prev_hash is None
    assert all(b.prev_hash == a.row_hash for a, b in zip(logs, logs[1:]))


def test_logs_in_one_flush_are_chained(app):
    db.session.add_all([AccessLog(user_id=1, door_id=1, success=True) for _ in range(3)])
    db.session.commit()
    assert verify_log_chain() == {"valid": True, "broken_at": None, "checked": 3}


def test_untouched_chain_is_valid(logs):
    assert verify_log_chain()["valid"]


def test_modified_row_detected(logs):
    raw("UPDATE access_logs SET success = 1 WHERE id = :id", id=logs[1].id)
    assert verify_log_chain() == {"valid": False, "broken_at": logs[1].id, "checked": 4}


def test_deleted_row_detected(logs):
    raw("DELETE FROM access_logs WHERE id = :id", id=logs[2].id)
    assert verify_log_chain()["broken_at"] == logs[3].id


def test_archived_prefix_still_valid(logs):
    raw("DELETE FROM access_logs WHERE id IN (:a, :b)", a=logs[0].id, b=logs[1].id)
    assert verify_log_chain()["valid"]


def test_existing_unsealed_logs_sealed_once(app):
    raw("INSERT INTO access_logs (user_id, door_id, timestamp, success) VALUES (1, 1, '2026-01-01 10:00:00.000000', 1)")
    raw("INSERT INTO access_logs (user_id, door_id, timestamp, success) VALUES (1, 1, '2026-01-02 10:00:00.000000', 0)")
    assert seal_existing_logs() == 2 and verify_log_chain()["valid"]
    raw("UPDATE access_logs SET row_hash = NULL WHERE id = 2")
    assert seal_existing_logs() == 0 and not verify_log_chain()["valid"]


def test_verify_endpoint_management_only(make_user, login, client, logs):
    login(make_user("management"))
    assert client.get("/logs/verify").json["valid"] is True
