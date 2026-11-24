from datetime import date, timedelta
import pytest
from models import MoveRequest, Notification


@pytest.fixture
def ben(make_user, login):
    user = make_user(unit_number="2B", floor=2)
    login(user)
    return user


@pytest.fixture
def maya(make_user):
    return make_user("management")


def ask(client, day=None, slot="Morning", kind="Move-in"):
    day = day or date.today() + timedelta(days=3)
    return client.post("/services/moves", data={"kind": kind, "date": day.isoformat(), "slot": slot})


def test_request_is_pending(client, ben):
    assert ask(client).status_code == 302
    move = MoveRequest.query.one()
    assert (move.resident_id, move.unit_number, move.kind, move.slot, move.status) == (ben.id, "2B", "Move-in", "Morning", "Pending")
    assert "Waiting for management" in client.get("/services/moves").data.decode()
    assert ask(client, day=date.today() - timedelta(days=1)).status_code == 400
    assert ask(client, slot="Midnight").status_code == 400


def test_approval_reserves_slot_and_notifies(client, ben, maya, login):
    ask(client)
    move = MoveRequest.query.one()
    login(maya)
    client.post(f"/services/moves/{move.id}/approve")
    assert move.status == "Approved" and move.decided_by == maya.id
    assert "was approved" in Notification.query.filter_by(user_id=ben.id).one().message


def test_clashing_approval_refused(client, ben, maya, make_user, login):
    ask(client)
    login(make_user(unit_number="2A", floor=2))
    ask(client)
    first, second = MoveRequest.query.order_by(MoveRequest.id).all()
    login(maya)
    client.post(f"/services/moves/{first.id}/approve")
    res = client.post(f"/services/moves/{second.id}/approve")
    assert res.status_code == 400 and b"already has the service elevator" in res.data
    assert second.status == "Pending"


def test_rejection_needs_reason_and_resident_sees_it(client, ben, maya, login):
    ask(client)
    move = MoveRequest.query.one()
    login(maya)
    assert client.post(f"/services/moves/{move.id}/reject").status_code == 400
    client.post(f"/services/moves/{move.id}/reject", data={"reason": "Elevator maintenance that morning"})
    assert move.status == "Rejected"
    login(ben)
    assert "Elevator maintenance that morning" in client.get("/services/moves").data.decode()


def test_todays_approved_move_on_front_desk(client, ben, maya, make_user, login):
    ask(client, day=date.today(), slot="Afternoon")
    login(maya)
    client.post(f"/services/moves/{MoveRequest.query.one().id}/approve")
    login(make_user("concierge"))
    page = client.get("/dashboard").data.decode()
    assert "Today's Moves" in page and "Move-in · Afternoon" in page


def test_only_management_decides(client, ben, make_user, login):
    ask(client)
    move = MoveRequest.query.one()
    for user in (make_user("concierge"), ben):
        login(user)
        assert client.post(f"/services/moves/{move.id}/approve").status_code == 403
    assert move.status == "Pending"
