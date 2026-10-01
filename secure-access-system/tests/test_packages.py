from datetime import datetime, timedelta
import pytest
from models import Notification, Package


@pytest.fixture
def aisha(make_user):
    return make_user(unit_number="2A")


@pytest.fixture
def concierge(make_user, login):
    user = make_user("concierge")
    login(user)
    return user


def log(client, unit="2A", carrier="Amazon", description="Small box"):
    return client.post("/desk/packages", data={"unit": unit, "carrier": carrier, "description": description})


def test_logged_package_is_waiting_for_unit(client, aisha, concierge):
    assert log(client, unit="2a").status_code == 302
    package = Package.query.one()
    assert (package.unit_number, package.carrier, package.logged_by, package.picked_up_at) == ("2A", "Amazon", concierge.id, None)
    page = client.get("/desk/packages").data.decode()
    assert "Small box" in page and "Picked Up" in page


def test_invalid_package_rejected(client, aisha, concierge):
    assert log(client, unit="9Z").status_code == 400
    assert log(client, carrier="Pigeon").status_code == 400
    assert log(client, description="").status_code == 400
    assert Package.query.count() == 0


def test_resident_sees_waiting_package_and_notification(client, aisha, concierge, login):
    log(client)
    assert Notification.query.filter_by(user_id=aisha.id).count() == 1
    login(aisha)
    page = client.get("/dashboard").data.decode()
    assert "1 waiting" in page and "Small box" in page and "waiting for you at the front desk" in page


def test_pickup_records_time_and_staff_and_moves_to_history(client, aisha, concierge, login):
    log(client)
    package = Package.query.one()
    client.post(f"/desk/packages/{package.id}/pickup")
    assert package.released_by == concierge.id and datetime.utcnow() - package.picked_up_at < timedelta(minutes=1)
    page = client.get("/desk/packages?unit=2a").data.decode()
    assert "No packages waiting" in page and "released by concierge test" in page
    login(aisha)
    assert "No packages waiting for you" in client.get("/dashboard").data.decode()


def test_residents_and_guests_cannot_log_or_release(client, aisha, concierge, make_user, login):
    log(client)
    package = Package.query.one()
    for user in (aisha, make_user("guest", access_expires_at=datetime.utcnow() + timedelta(days=1))):
        login(user)
        assert log(client).status_code == 403
        assert client.post(f"/desk/packages/{package.id}/pickup").status_code == 403
        assert client.get("/desk/packages").status_code == 403
    assert Package.query.count() == 1 and package.picked_up_at is None
