import pytest
from models import MaintenanceRequest, Notification


@pytest.fixture
def aisha(make_user, login):
    user = make_user(unit_number="2A", floor=2)
    login(user)
    return user


def submit(client, entry=True, category="Plumbing", description="Kitchen tap drips constantly"):
    data = {"category": category, "description": description}
    if entry:
        data["entry"] = "on"
    return client.post("/services/maintenance", data=data)


def test_resident_submits_open_request(client, aisha):
    assert submit(client).status_code == 302
    item = MaintenanceRequest.query.one()
    assert (item.resident_id, item.unit_number, item.category, item.status, item.entry_allowed) == (aisha.id, "2A", "Plumbing", "Open", True)
    page = client.get("/services/maintenance").data.decode()
    assert "Kitchen tap drips constantly" in page and ">Open<" in page
    assert submit(client, category="Gardening").status_code == 400
    assert submit(client, description="").status_code == 400


def test_status_change_shown_and_notified(client, aisha, make_user, login):
    submit(client)
    item = MaintenanceRequest.query.one()
    login(make_user("management"))
    client.post(f"/services/maintenance/{item.id}/status", data={"status": "In Progress"})
    assert item.status == "In Progress"
    assert Notification.query.filter_by(user_id=aisha.id).one().message.endswith("is now In Progress.")
    client.post(f"/services/maintenance/{item.id}/status", data={"status": "Done"})
    assert item.status == "In Progress"
    login(aisha)
    assert ">In Progress<" in client.get("/services/maintenance").data.decode()


def test_staff_see_entry_permission(client, aisha, make_user, login):
    submit(client)
    submit(client, entry=False, description="Bathroom fan noisy")
    login(make_user("concierge"))
    board = client.get("/services/maintenance").data.decode()
    assert board.count("Entry permitted") == 1 and "Resident must be home" in board
    allowed = MaintenanceRequest.query.filter_by(entry_allowed=True).one()
    assert "Entry permitted: staff may enter" in client.get(f"/services/maintenance/{allowed.id}").data.decode()


def test_other_residents_denied(client, aisha, make_user, login):
    submit(client)
    item = MaintenanceRequest.query.one()
    login(make_user(unit_number="2B", floor=2))
    assert client.get(f"/services/maintenance/{item.id}").status_code == 403
    assert "Kitchen tap drips constantly" not in client.get("/services/maintenance").data.decode()
    assert client.post(f"/services/maintenance/{item.id}/status", data={"status": "Completed"}).status_code == 403
