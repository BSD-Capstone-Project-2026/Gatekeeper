from datetime import datetime, timedelta
import pytest
from models import db, ParkingPermit


@pytest.fixture
def ben(make_user, login):
    user = make_user(unit_number="2B")
    login(user)
    return user


def register(client, plate="abcd 123", hours=4):
    return client.post("/visitors/parking", data={"plate": plate, "hours": hours})


@pytest.mark.parametrize("hours", [2, 4, 24])
def test_register_permit_for_allowed_durations(client, ben, hours):
    assert register(client, hours=hours).status_code == 302
    permit = ParkingPermit.query.one()
    assert permit.plate == "ABCD 123" and permit.is_active
    assert timedelta(hours=hours) - timedelta(minutes=1) < permit.ends_at - datetime.utcnow() <= timedelta(hours=hours)


def test_other_durations_rejected(client, ben):
    assert register(client, hours=12).status_code == 400 and ParkingPermit.query.count() == 0


def test_concierge_search_shows_status_and_unit(client, ben, make_user, login):
    register(client)
    login(make_user("concierge"))
    page = client.get("/visitors/parking?plate=abcd123").data.decode()
    assert "Active permit" in page and "Unit 2B" in page


def test_limit_of_two_active_permits(client, ben):
    register(client, "AAA 111")
    register(client, "BBB 222")
    res = register(client, "CCC 333")
    assert res.status_code == 400 and b"Limit of 2 active permits reached" in res.data
    assert ParkingPermit.query.count() == 2


def test_expired_permit_shown_as_expired(client, ben, make_user, login):
    register(client)
    permit = ParkingPermit.query.one()
    permit.ends_at = datetime.utcnow() - timedelta(minutes=1)
    db.session.commit()
    assert "Expired" in client.get("/visitors/parking").data.decode()
    assert register(client, "NEW 1").status_code == 302
    login(make_user("concierge"))
    assert "Permit expired" in client.get("/visitors/parking?plate=ABCD123").data.decode()


def test_unknown_plate_and_permissions(client, make_user, login):
    login(make_user("concierge"))
    assert "No permit found" in client.get("/visitors/parking?plate=ZZZ999").data.decode()
    assert register(client).status_code == 403
    login(make_user("cleaner"))
    assert client.get("/visitors/parking").status_code == 403
