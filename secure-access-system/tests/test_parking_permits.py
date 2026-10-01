from datetime import datetime, timedelta
import pytest
from models import db, ParkingPermit


@pytest.fixture
def ben(make_user, login):
    user = make_user(unit_number="2B")
    login(user)
    return user


def register(client, plate="abcd 123", hours=4, name="Sam Lee"):
    return client.post("/visitors/parking", data={"plate": plate, "hours": hours, "visitor_name": name})


def as_concierge(make_user, login):
    concierge = make_user("concierge")
    login(concierge)
    return concierge


def test_request_is_pending_with_code_and_qr(client, ben):
    assert register(client).status_code == 302
    permit = ParkingPermit.query.one()
    assert (permit.plate, permit.visitor_name, permit.current_status, len(permit.code)) == ("ABCD 123", "Sam Lee", "pending", 8)
    page = client.get("/visitors/parking").data.decode()
    assert "Waiting for the front desk" in page and permit.code in page
    svg = client.get(f"/visitors/parking/{permit.id}/qr.svg")
    assert svg.mimetype == "image/svg+xml" and b"<svg" in svg.data


@pytest.mark.parametrize("hours", [2, 4, 24])
def test_concierge_approval_starts_the_permit(client, ben, make_user, login, hours):
    register(client, hours=hours)
    permit = ParkingPermit.query.one()
    concierge = as_concierge(make_user, login)
    page = client.get(f"/visitors/parking?q={permit.code.lower()}").data.decode()
    assert "Sam Lee" in page and "Unit 2B" in page and "Approve" in page
    client.post(f"/visitors/parking/{permit.id}/approve")
    assert permit.is_active and permit.decided_by == concierge.id
    assert timedelta(hours=hours) - timedelta(minutes=1) < permit.ends_at - datetime.utcnow() <= timedelta(hours=hours)
    assert "Active permit" in client.get("/visitors/parking?q=abcd123").data.decode()


def test_declined_permit_shown_to_resident(client, ben, make_user, login):
    register(client)
    permit = ParkingPermit.query.one()
    as_concierge(make_user, login)
    client.post(f"/visitors/parking/{permit.id}/decline")
    client.post(f"/visitors/parking/{permit.id}/approve")
    assert permit.current_status == "declined"
    login(ben)
    assert "Declined by the front desk" in client.get("/visitors/parking").data.decode()


def test_other_durations_and_missing_name_rejected(client, ben):
    assert register(client, hours=12).status_code == 400
    assert register(client, name="").status_code == 400
    assert ParkingPermit.query.count() == 0


def test_limit_counts_pending_and_active_permits(client, ben):
    register(client, "AAA 111")
    register(client, "BBB 222")
    res = register(client, "CCC 333")
    assert res.status_code == 400 and b"Limit of 2 active permits reached" in res.data
    assert ParkingPermit.query.count() == 2


def test_expired_and_lapsed_permits(client, ben, make_user, login):
    register(client)
    register(client, "LATE 1")
    approved, lapsed = ParkingPermit.query.order_by(ParkingPermit.id).all()
    approved.status = "approved"
    for permit in (approved, lapsed):
        permit.ends_at = datetime.utcnow() - timedelta(minutes=1)
    db.session.commit()
    page = client.get("/visitors/parking").data.decode()
    assert "Not approved in time" in page and "Expired" in page
    assert register(client, "NEW 1").status_code == 302
    as_concierge(make_user, login)
    assert "Permit expired" in client.get("/visitors/parking?q=ABCD123").data.decode()
    assert client.post(f"/visitors/parking/{lapsed.id}/approve").status_code == 302 and lapsed.current_status == "lapsed"


def test_unknown_code_and_permissions(client, ben, make_user, login):
    register(client)
    permit = ParkingPermit.query.one()
    assert client.post(f"/visitors/parking/{permit.id}/approve").status_code == 403
    as_concierge(make_user, login)
    assert "No permit found" in client.get("/visitors/parking?q=ZZZ999").data.decode()
    assert register(client).status_code == 403
    login(make_user("cleaner"))
    assert client.get("/visitors/parking").status_code == 403
