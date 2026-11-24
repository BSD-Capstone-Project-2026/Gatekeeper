from datetime import datetime, timedelta
import pytest
from models import db, Announcement, AnnouncementRead


@pytest.fixture
def residents(make_user):
    return make_user(unit_number="2A", floor=2), make_user(unit_number="6A", floor=6)


@pytest.fixture
def maya(make_user, login):
    user = make_user("management")
    login(user)
    return user


def publish(client, floors=("2",), expires="", title="Water off Friday 10-12"):
    return client.post("/services/announcements", data={"title": title, "body": "Plumbing work on the riser.", "floors": list(floors),
                                                         "expires": expires, "tz_offset": "0"})


def test_floor_announcement_reaches_only_those_floors(client, residents, maya, login):
    assert publish(client).status_code == 302
    assert Announcement.query.one().floor_list == [2]
    floor2, floor6 = residents
    login(floor2)
    assert "Water off Friday" in client.get("/services/announcements").data.decode()
    login(floor6)
    assert "Water off Friday" not in client.get("/services/announcements").data.decode()
    assert client.get(f"/services/announcements/{Announcement.query.one().id}").status_code == 404


def test_all_floors_and_invalid_input(client, residents, maya, login):
    assert publish(client, floors=("all",)).status_code == 302
    assert publish(client, floors=()).status_code == 400
    assert publish(client, expires="2001-01-01").status_code == 400
    login(residents[1])
    assert "Water off Friday" in client.get("/services/announcements").data.decode()


def test_expired_announcement_hidden(client, residents, maya, login):
    publish(client, expires=(datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d"))
    item = Announcement.query.one()
    item.expires_at = datetime.utcnow() - timedelta(minutes=1)
    db.session.commit()
    assert "expired" in client.get("/services/announcements").data.decode()
    login(residents[0])
    assert "Water off Friday" not in client.get("/services/announcements").data.decode()
    assert "Water off Friday" not in client.get("/dashboard").data.decode()


def test_unread_until_opened(client, residents, maya, login):
    publish(client)
    item = Announcement.query.one()
    login(residents[0])
    home = client.get("/dashboard").data.decode()
    assert "Water off Friday" in home and 'aria-label="Unread"' in home
    assert "Plumbing work on the riser." in client.get(f"/services/announcements/{item.id}").data.decode()
    assert AnnouncementRead.query.filter_by(user_id=residents[0].id).count() == 1
    assert "Water off Friday" not in client.get("/dashboard").data.decode()
    assert 'aria-label="Unread"' not in client.get("/services/announcements").data.decode()


def test_only_management_publishes(client, residents, make_user, login):
    for user in (make_user("concierge"), residents[0]):
        login(user)
        assert publish(client).status_code == 403
    assert Announcement.query.count() == 0
