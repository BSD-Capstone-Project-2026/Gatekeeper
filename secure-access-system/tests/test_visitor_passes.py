from datetime import datetime, timedelta
import pytest
from models import db, AccessLog, VisitorPass
from utils.log_integrity import verify_log_chain


def local(dt):
    return dt.strftime("%Y-%m-%dT%H:%M")


def create(client, name="Sam Lee", start=None, end=None):
    start = start or datetime.utcnow() - timedelta(minutes=1)
    end = end or datetime.utcnow() + timedelta(hours=4)
    return client.post("/visitors/passes", data={"visitor_name": name, "valid_from": local(start), "valid_until": local(end), "tz_offset": "0"})


@pytest.fixture
def resident(make_user, login):
    user = make_user(unit_number="2A", email="aisha.khan@gatekeeper.demo")
    login(user)
    return user


def check(client, make_user, login, code):
    login(make_user("concierge"))
    return client.post("/visitors/passes/check", data={"code": code})


def test_resident_creates_pass_with_qr(client, resident):
    assert create(client).status_code == 302
    visitor_pass = VisitorPass.query.one()
    assert len(visitor_pass.code) == 8 and visitor_pass.status == "Active"
    page = client.get("/visitors/passes").data.decode()
    assert "Sam Lee" in page and visitor_pass.code in page
    svg = client.get(f"/visitors/passes/{visitor_pass.id}/qr.svg")
    assert svg.mimetype == "image/svg+xml" and b"<svg" in svg.data


@pytest.mark.parametrize("days, ok", [(7, True), (8, False)])
def test_pass_limited_to_seven_days(client, resident, days, ok):
    start = datetime.utcnow()
    create(client, start=start, end=start + timedelta(days=days))
    assert (VisitorPass.query.count() == 1) is ok


def test_valid_pass_admits_and_logs_visitor(client, resident, make_user, login, main_door):
    create(client)
    code = VisitorPass.query.one().code
    res = check(client, make_user, login, code)
    assert res.status_code == 200 and b"Admit Sam Lee" in res.data and b"Unit 2A" in res.data
    log = AccessLog.query.one()
    assert (log.user_id, log.door_id, log.visitor_name, log.success) == (resident.id, main_door.id, "Sam Lee", True)
    assert verify_log_chain()["valid"]


def test_expired_pass_refused(client, resident, make_user, login, main_door):
    create(client)
    visitor_pass = VisitorPass.query.one()
    visitor_pass.valid_until = datetime.utcnow() - timedelta(minutes=1)
    db.session.commit()
    res = check(client, make_user, login, visitor_pass.code)
    assert res.status_code == 422 and b"Pass expired" in res.data
    assert AccessLog.query.one().failure_reason == "Pass expired"


def test_revoked_pass_refused(client, resident, make_user, login, main_door):
    create(client)
    visitor_pass = VisitorPass.query.one()
    client.post(f"/visitors/passes/{visitor_pass.id}/revoke")
    assert b"Pass revoked" in check(client, make_user, login, visitor_pass.code).data


def test_residents_see_only_their_own_passes(client, resident, make_user, login):
    create(client, name="Aisha Visitor")
    login(make_user(unit_number="2B"))
    page = client.get("/visitors/passes").data.decode()
    assert "Aisha Visitor" not in page
    other = VisitorPass.query.one()
    assert client.post(f"/visitors/passes/{other.id}/revoke").status_code == 404


def test_only_staff_can_check_and_only_residents_create(client, make_user, login):
    login(make_user())
    assert client.post("/visitors/passes/check", data={"code": "ANYTHING"}).status_code == 403
    login(make_user("concierge"))
    assert create(client).status_code == 403
    login(make_user("guest", access_expires_at=datetime.utcnow() + timedelta(days=1)))
    assert client.get("/visitors/passes").status_code == 403
