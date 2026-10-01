from datetime import datetime, timedelta
import pytest
from models import db, BuildingKey, KeyLoan


@pytest.fixture
def priya(make_user, login):
    user = make_user("concierge")
    login(user)
    return user


@pytest.fixture
def boiler(app):
    key = BuildingKey(name="Boiler Room", location="Basement")
    db.session.add(key)
    db.session.commit()
    return key


def sign_out(client, key, hours=2):
    due = datetime.utcnow() + timedelta(hours=hours)
    return client.post(f"/desk/keys/{key.id}/sign-out", data={"contractor": "Mike Ross", "company": "CoolAir HVAC", "purpose": "Boiler service",
                                                             "expected_return": due.strftime("%Y-%m-%dT%H:%M"), "tz_offset": "0"})


def test_sign_out_marks_key_out(client, priya, boiler):
    assert boiler.status == "In"
    assert sign_out(client, boiler).status_code == 302
    loan = KeyLoan.query.one()
    assert (loan.contractor, loan.company, loan.purpose, loan.signed_out_by) == ("Mike Ross", "CoolAir HVAC", "Boiler service", priya.id)
    assert boiler.status == "Out"
    page = client.get("/desk/keys").data.decode()
    assert "Mike Ross · CoolAir HVAC" in page and "Return" in page


def test_sign_out_requires_every_field_future_time_and_free_key(client, priya, boiler):
    assert sign_out(client, boiler, hours=-1).status_code == 400
    assert client.post(f"/desk/keys/{boiler.id}/sign-out", data={"contractor": "Mike"}).status_code == 400
    sign_out(client, boiler)
    res = sign_out(client, boiler)
    assert res.status_code == 400 and b"already signed out" in res.data
    assert KeyLoan.query.count() == 1


def test_return_records_time_and_staff(client, priya, boiler, make_user, login):
    sign_out(client, boiler)
    lucas = make_user("concierge")
    login(lucas)
    loan = KeyLoan.query.one()
    client.post(f"/desk/keys/loans/{loan.id}/return")
    assert loan.received_by == lucas.id and datetime.utcnow() - loan.returned_at < timedelta(minutes=1)
    assert boiler.status == "In"
    assert "received by concierge test" in client.get("/desk/keys").data.decode()


def test_late_key_marked_overdue(client, priya, boiler):
    sign_out(client, boiler)
    KeyLoan.query.one().expected_return = datetime.utcnow() - timedelta(minutes=5)
    db.session.commit()
    assert boiler.status == "Overdue"
    assert "is-overdue" in client.get("/desk/keys").data.decode()


def test_staff_add_keys_and_residents_denied(client, priya, boiler, make_user, login):
    assert client.post("/desk/keys", data={"name": "Roof Access", "location": "Roof"}).status_code == 302
    assert client.post("/desk/keys", data={"name": "boiler room"}).status_code == 400
    login(make_user(unit_number="2A"))
    assert client.get("/desk/keys").status_code == 403
    assert sign_out(client, boiler).status_code == 403
    assert BuildingKey.query.count() == 2 and KeyLoan.query.count() == 0
