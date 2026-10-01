from datetime import datetime, timedelta
import pytest
from models import LostItem


@pytest.fixture
def priya(make_user, login):
    user = make_user("concierge")
    login(user)
    return user


def log(client, description="Black umbrella", location="Lobby", notes="Found by the mailboxes"):
    return client.post("/desk/lost-found", data={"description": description, "location": location, "notes": notes})


def test_logged_item_listed_as_unclaimed(client, priya):
    assert log(client).status_code == 302
    item = LostItem.query.one()
    assert (item.description, item.found_location, item.logged_by, item.returned_at) == ("Black umbrella", "Lobby", priya.id, None)
    page = client.get("/desk/lost-found").data.decode()
    assert "Unclaimed · 1" in page and "Black umbrella" in page and "Found by the mailboxes" in page
    assert log(client, location="").status_code == 400


def test_residents_see_unclaimed_items_without_staff_notes(client, priya, make_user, login):
    log(client)
    login(make_user(unit_number="2B"))
    page = client.get("/desk/lost-found").data.decode()
    assert "Black umbrella" in page and "Lobby" in page and "Found by the mailboxes" not in page
    assert "Mark Returned" not in page and "Log Item" not in page


def test_mark_returned_records_claimant_time_and_staff(client, priya):
    log(client)
    item = LostItem.query.one()
    assert client.post(f"/desk/lost-found/{item.id}/return", data={"claimant": ""}).status_code == 400
    client.post(f"/desk/lost-found/{item.id}/return", data={"claimant": "Ben Carter"})
    assert (item.claimant_name, item.returned_by) == ("Ben Carter", priya.id)
    assert datetime.utcnow() - item.returned_at < timedelta(minutes=1)
    page = client.get("/desk/lost-found").data.decode()
    assert "Unclaimed · 0" in page and "Returned to Ben Carter" in page


def test_residents_cannot_log_or_return(client, priya, make_user, login):
    log(client)
    item = LostItem.query.one()
    login(make_user(unit_number="2B"))
    assert log(client).status_code == 403
    assert client.post(f"/desk/lost-found/{item.id}/return", data={"claimant": "Me"}).status_code == 403
    login(make_user("guest", access_expires_at=datetime.utcnow() + timedelta(days=1)))
    assert client.get("/desk/lost-found").status_code == 403
    assert LostItem.query.count() == 1 and item.returned_at is None
