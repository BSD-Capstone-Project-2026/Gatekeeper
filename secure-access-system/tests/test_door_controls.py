import pytest
from models import db, AuditLog, Door, add_missing_columns


@pytest.mark.parametrize("role", ["concierge", "management"])
def test_staff_see_doors_with_state(make_user, login, client, main_door, role):
    login(make_user(role))
    page = client.get("/door-controls").data
    assert b"Main Entrance" in page and b"Locked" in page


def test_unlock_then_lock_changes_state_and_audits(make_user, login, client, main_door):
    staff = make_user("concierge")
    login(staff)
    assert client.post(f"/doors/{main_door.id}/unlock").status_code == 302
    db.session.refresh(main_door)
    assert main_door.is_locked is False
    assert b"Unlocked" in client.get("/door-controls").data
    client.post(f"/doors/{main_door.id}/lock")
    db.session.refresh(main_door)
    assert main_door.is_locked is True
    actions = [(a.action, a.door_id, a.performed_by) for a in AuditLog.query.order_by(AuditLog.id)]
    assert actions == [("door_unlock", main_door.id, staff.id), ("door_lock", main_door.id, staff.id)]


def test_resident_cannot_control_doors(make_user, login, client, main_door):
    login(make_user())
    assert client.post(f"/doors/{main_door.id}/unlock").status_code == 403
    assert client.get("/door-controls").status_code == 403
    db.session.refresh(main_door)
    assert main_door.is_locked is True
    assert AuditLog.query.filter_by(action="access_denied").count() == 2


def test_unknown_action_rejected(make_user, login, client, main_door):
    login(make_user("concierge"))
    assert client.post(f"/doors/{main_door.id}/open").status_code == 404


def test_new_column_gets_default_on_existing_rows(app, main_door):
    db.session.execute(db.text("ALTER TABLE doors DROP COLUMN is_locked"))
    db.session.commit()
    add_missing_columns()
    db.session.expire_all()
    assert Door.query.get(main_door.id).is_locked is True
