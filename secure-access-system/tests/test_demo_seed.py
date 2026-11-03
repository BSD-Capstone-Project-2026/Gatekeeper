from models import User, Door, Zone, AccessLog, Incident, Notification, EntryRequest, ParkingPermit, VisitorPass, WatchlistEntry
from scripts.seed_demo import seed_demo, DOMAIN
from utils.log_integrity import verify_log_chain


def demo_count(role):
    return User.query.filter(User.email.like(f"%@{DOMAIN}"), User.role == role).count()


def test_seed_creates_building_and_people(app):
    seed_demo("Demo@2026")
    assert [demo_count(r) for r in ("resident", "concierge", "management", "guest", "cleaner")] == [10, 2, 2, 1, 1]
    floors = {u.floor for u in User.query.filter_by(role="resident")}
    assert floors == {2, 3, 4, 5, 6}
    assert Door.query.filter_by(door_type="unit").count() == 10 and Door.query.filter_by(door_type="common").count() == 3
    assert {z.name for z in Zone.query} == {"Ground", "Gym", "Amenities", "Rooftop"}
    assert all(len(u.zones) >= 3 for u in User.query.filter_by(role="resident"))


def test_seed_adds_history_incident_and_notification(app):
    seed_demo("Demo@2026")
    assert AccessLog.query.count() > 100
    incident = Incident.query.filter_by(status="open").one()
    assert Notification.query.filter_by(incident_id=incident.id).count() == 1
    assert verify_log_chain()["valid"]


def test_seed_is_repeatable(app):
    seed_demo("Demo@2026")
    counts = (User.query.count(), Door.query.count(), AccessLog.query.count(), Incident.query.count())
    assert seed_demo("Demo@2026")["created_users"] == 0
    assert (User.query.count(), Door.query.count(), AccessLog.query.count(), Incident.query.count()) == counts


def test_demo_accounts_can_sign_in(app, client):
    seed_demo("Demo@2026")
    res = client.post("/login", data={"email": f"priya.sharma@{DOMAIN}", "password": "Demo@2026"})
    assert res.location.endswith("/dashboard")


def test_seed_adds_visitor_examples_once(app):
    seed_demo("Demo@2026")
    counts = [t.query.count() for t in (VisitorPass, EntryRequest, ParkingPermit, WatchlistEntry)]
    assert all(counts)
    seed_demo("Demo@2026")
    assert [t.query.count() for t in (VisitorPass, EntryRequest, ParkingPermit, WatchlistEntry)] == counts
    assert {p.status for p in VisitorPass.query} == {"Checked in", "Scheduled", "Active", "Expired", "Revoked"}
