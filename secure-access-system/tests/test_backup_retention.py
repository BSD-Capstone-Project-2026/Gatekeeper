import os
import sqlite3
from datetime import datetime, timedelta
import pytest
from app import archive_old_logs, run_in_context
from models import db, AccessLog, AccessLogArchive
from scripts.backup import backup_database
from scripts.restore import restore_database


def rows(path):
    conn = sqlite3.connect(path)
    result = conn.execute("SELECT name FROM t ORDER BY name").fetchall()
    conn.close()
    return result


@pytest.fixture
def live_db(tmp_path):
    path = tmp_path / "live.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE t (name TEXT)")
    conn.execute("INSERT INTO t VALUES ('original')")
    conn.commit()
    conn.close()
    return str(path)


def test_backup_copies_live_database(live_db, tmp_path):
    backup = backup_database(live_db, tmp_path / "backups")
    assert rows(backup) == [("original",)]


def test_only_newest_backups_kept(live_db, tmp_path):
    made = [backup_database(live_db, tmp_path / "backups", keep=2) for _ in range(4)]
    kept = sorted(p.name for p in (tmp_path / "backups").iterdir())
    assert kept == sorted(os.path.basename(p) for p in made[-2:])


def test_restore_returns_database_to_backup_state(live_db, tmp_path):
    backup = backup_database(live_db, tmp_path / "backups")
    conn = sqlite3.connect(live_db)
    conn.execute("DELETE FROM t")
    conn.commit()
    conn.close()
    restore_database(backup, live_db)
    assert rows(live_db) == [("original",)]


def test_restore_rejects_corrupt_backup(live_db, tmp_path):
    bad = tmp_path / "bad.db"
    bad.write_bytes(b"not a database")
    with pytest.raises(Exception):
        restore_database(str(bad), live_db)
    assert rows(live_db) == [("original",)]


def test_old_logs_archived_with_user(app, make_user):
    user = make_user()
    db.session.add_all([
        AccessLog(user_id=user.id, door_id=1, timestamp=datetime.utcnow() - timedelta(days=91), success=True),
        AccessLog(user_id=user.id, door_id=1, timestamp=datetime.utcnow(), success=True),
    ])
    db.session.commit()
    run_in_context(app, archive_old_logs)
    assert AccessLog.query.count() == 1
    assert AccessLogArchive.query.one().user_id == user.id
