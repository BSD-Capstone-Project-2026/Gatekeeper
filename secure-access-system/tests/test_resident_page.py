from models import db, Door, AccessLog


def unit_resident(make_user):
    door = Door(name="Unit 7C Door", door_type="unit", associated_unit="7C")
    db.session.add(door)
    db.session.commit()
    return make_user(unit_number="7C", floor=7, door_id=door.id)


def test_access_page_shows_three_tiles(make_user, login, client, main_door):
    login(unit_resident(make_user))
    page = client.get("/simulate").data.decode()
    assert page.count("access-tile") == 3
    assert "Main Entrance" in page and "Elevator" in page and "Unit 7C" in page
    assert 'class="app-nav"' in page and "🚪" not in page


def test_resident_without_unit_gets_no_unit_tile(make_user, login, client, main_door):
    login(make_user())
    page = client.get("/simulate").data.decode()
    assert page.count("access-tile") == 2 and "const UNIT_DOOR_ID = null;" in page


def test_touch_targets_and_state_styles(client):
    css = client.get("/static/css/app.css").data
    assert b"min-height: 44px" in css and b".access-tile" in css


def test_history_shows_outcome_badges(make_user, login, client, main_door):
    user = make_user()
    db.session.add_all([AccessLog(user_id=user.id, door_id=main_door.id, success=True, wifi_verified=True, proximity_verified=True),
                        AccessLog(user_id=user.id, door_id=main_door.id, success=False, wifi_verified=False, proximity_verified=True)])
    db.session.commit()
    login(user)
    page = client.get("/profile/incidents").data
    assert b"badge bg-success\">Unlocked" in page and b"badge bg-danger\">Denied" in page and b"network not trusted" in page
