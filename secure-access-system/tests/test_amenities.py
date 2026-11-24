from datetime import datetime, timedelta
import pytest
from models import db, AccessLog, Amenity, AmenityBooking, Door


@pytest.fixture
def gym(app):
    door = Door(name="Gym Door", location="Level 1", door_type="common", is_active=True)
    db.session.add(door)
    db.session.flush()
    amenity = Amenity(name="Gym", door_id=door.id, opens_hour=0, closes_hour=24, capacity=1)
    db.session.add_all([amenity, Amenity(name="Party Room", opens_hour=0, closes_hour=24, capacity=2)])
    db.session.commit()
    return amenity


@pytest.fixture
def aisha(make_user, login):
    user = make_user(unit_number="2A", floor=2)
    login(user)
    return user


def hour(offset=0):
    return datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=offset)


def book(client, amenity, start):
    return client.post("/services/amenities/book", data={"amenity": amenity.id, "start": start.strftime("%Y-%m-%dT%H:%M")})


def test_booking_an_available_slot_is_confirmed(client, gym, aisha):
    assert book(client, gym, hour(2)).status_code == 302
    booking = AmenityBooking.query.one()
    assert (booking.user_id, booking.starts_at, booking.ends_at - booking.starts_at) == (aisha.id, hour(2), timedelta(hours=1))
    page = client.get(f"/services/amenities?amenity={gym.id}&day={hour(2):%Y-%m-%d}").data.decode()
    assert "Booked" in page and "My bookings" in page
    assert book(client, gym, hour(-2)).status_code == 400


def test_full_slot_and_overlapping_booking_refused(client, gym, aisha, make_user, login):
    book(client, gym, hour(2))
    party = Amenity.query.filter_by(name="Party Room").one()
    res = book(client, party, hour(2))
    assert res.status_code == 400 and b"You already have a booking at this time" in res.data
    login(make_user(unit_number="2B", floor=2))
    res = book(client, gym, hour(2))
    assert res.status_code == 400 and b"This gym slot is full" in res.data
    assert AmenityBooking.query.count() == 1


def test_door_opens_during_booking(client, gym, aisha, request_door):
    book(client, gym, hour(0))
    res = request_door(aisha, gym.door)
    assert res.status_code == 200 and AccessLog.query.one().success


def test_door_refused_without_active_booking(client, gym, aisha, request_door):
    res = request_door(aisha, gym.door)
    assert res.status_code == 403 and res.json["reason"] == "No active booking"
    book(client, gym, hour(3))
    assert request_door(aisha, gym.door).json["reason"] == "No active booking"
    assert AccessLog.query.filter_by(failure_reason="No active booking").count() == 2


def test_cancelled_slot_frees_up(client, gym, aisha, make_user, login):
    book(client, gym, hour(2))
    booking = AmenityBooking.query.one()
    client.post(f"/services/amenities/bookings/{booking.id}/cancel")
    assert booking.cancelled_at is not None
    login(make_user(unit_number="2B", floor=2))
    assert book(client, gym, hour(2)).status_code == 302


def test_staff_see_todays_bookings_and_cannot_book(client, gym, aisha, make_user, login):
    book(client, gym, hour(0))
    login(make_user("concierge"))
    page = client.get("/services/amenities").data.decode()
    assert "resident test" in page and "2A" in page
    assert book(client, gym, hour(3)).status_code == 403
