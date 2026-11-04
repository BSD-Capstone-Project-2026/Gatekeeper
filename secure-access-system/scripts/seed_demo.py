import os
import secrets
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db, User, Door, Zone, AccessLog, Incident, Notification, AuditLog, BuildingKey, EntryRequest, KeyLoan, LostItem, Package, ParkingPermit, ShiftLogEntry, VisitorPass, WatchlistEntry

DOMAIN = "gatekeeper.demo"
STAFF = [("management", "Maya", "Chen"), ("management", "Daniel", "Okafor"),
         ("concierge", "Priya", "Sharma"), ("concierge", "Lucas", "Martin")]
RESIDENTS = [("Aisha", "Khan"), ("Ben", "Carter"), ("Chloe", "Nguyen"), ("Diego", "Ramirez"), ("Emma", "Wilson"),
             ("Farhan", "Ali"), ("Grace", "Kim"), ("Hiro", "Tanaka"), ("Isabel", "Rossi"), ("Jamal", "Brooks")]
UNITS = [f"{floor}{letter}" for floor in range(2, 7) for letter in "AB"]
ZONES = {"Ground": "Ground floor", "Gym": "Fitness area", "Amenities": "Common amenities", "Rooftop": "Rooftop terrace"}
COMMON_DOORS = [("Gym Door", "Level 1", "Gym"), ("Amenities Room Door", "Level 1", "Amenities"), ("Rooftop Door", "Roof", "Rooftop")]
BUILDING_KEYS = [("Boiler Room", "Basement"), ("Electrical Room", "Basement"), ("Elevator Machine Room", "Roof"), ("Pool Pump Room", "Level 1"), ("Roof Access", "Roof")]


def get_or_create(model, lookup, **fields):
    record = model.query.filter_by(**lookup).first()
    if not record:
        record = model(**lookup, **fields)
        db.session.add(record)
        db.session.flush()
    return record


def demo_user(role, first, last, password, **fields):
    email = f"{first.lower()}.{last.lower()}@{DOMAIN}"
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(first_name=first, last_name=last, username=f"{first.lower()}.{last.lower()}", email=email, role=role, **fields)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
    return user


def seed_history(residents, unit_doors, main_door, gym_door, guest, concierge):
    now = datetime.utcnow()
    logs = []
    for days_ago in range(7, 0, -1):
        day = (now - timedelta(days=days_ago)).replace(hour=0, minute=0, second=0, microsecond=0)
        for i, resident in enumerate(residents):
            logs.append(AccessLog(user_id=resident.id, door_id=main_door.id, timestamp=day + timedelta(hours=8, minutes=i * 4), success=True,
                                  wifi_verified=True, proximity_verified=True, failure_reason=""))
            logs.append(AccessLog(user_id=resident.id, door_id=unit_doors[resident.unit_number].id, timestamp=day + timedelta(hours=18, minutes=i * 5),
                                  success=True, wifi_verified=True, proximity_verified=True, failure_reason=""))
        logs.append(AccessLog(user_id=residents[days_ago % len(residents)].id, door_id=gym_door.id, timestamp=day + timedelta(hours=7),
                              success=days_ago % 3 != 0, wifi_verified=days_ago % 3 != 0, proximity_verified=True,
                              failure_reason="" if days_ago % 3 else "network not trusted"))
    target = residents[4]
    attempts = [now - timedelta(minutes=m) for m in (95, 91, 88)]
    logs += [AccessLog(user_id=guest.id, door_id=unit_doors[target.unit_number].id, timestamp=t, success=False, wifi_verified=True,
                       proximity_verified=True, failure_reason="permission denied") for t in attempts]
    logs += [AccessLog(user_id=r.id, door_id=main_door.id, timestamp=now - timedelta(minutes=40 - 7 * i), success=True,
                       wifi_verified=True, proximity_verified=True, failure_reason="") for i, r in enumerate(residents[:5])]
    db.session.add_all(logs)
    incident = Incident(unit_number=target.unit_number, door_id=unit_doors[target.unit_number].id, incident_type="repeated_failed_attempts",
                        status="open", trigger_rule="3 failed attempts within 10 minutes", attempt_count=3,
                        first_attempt_time=attempts[0], last_attempt_time=attempts[-1])
    db.session.add(incident)
    db.session.flush()
    db.session.add(Notification(user_id=target.id, incident_id=incident.id, status="queued",
                                message=f"Security alert (repeated_failed_attempts): 3 failed attempts on Unit {target.unit_number} Door "
                                        f"(unit {target.unit_number}) at {attempts[-1]:%Y-%m-%d %H:%M} UTC."))
    db.session.add(AuditLog(user_id=concierge.id, performed_by=concierge.id, action="door_unlock", door_id=gym_door.id,
                            details="Door 'Gym Door' unlocked from the front desk", timestamp=now - timedelta(hours=3)))
    db.session.add(AuditLog(user_id=concierge.id, performed_by=concierge.id, action="door_lock", door_id=gym_door.id,
                            details="Door 'Gym Door' locked from the front desk", timestamp=now - timedelta(hours=2, minutes=45)))


def seed_visitors(staff, residents):
    maya, daniel, priya, lucas = staff
    aisha, ben, chloe, diego, emma, farhan, grace, hiro, isabel, jamal = residents
    now = datetime.utcnow()

    if not VisitorPass.query.filter_by(code="SAMLEE29").first():
        db.session.add_all([
            VisitorPass(code="SAMLEE29", resident_id=aisha.id, visitor_name="Sam Lee", valid_from=now - timedelta(hours=1),
                        valid_until=now + timedelta(hours=5), checked_in_at=now - timedelta(minutes=30), checked_in_by=priya.id),
            VisitorPass(code="JBLAKE29", resident_id=aisha.id, visitor_name="Jordan Blake", valid_from=now + timedelta(days=1),
                        valid_until=now + timedelta(days=1, hours=4)),
            VisitorPass(code="NPATEL29", resident_id=ben.id, visitor_name="Nora Patel", valid_from=now - timedelta(minutes=30), valid_until=now + timedelta(hours=6)),
            VisitorPass(code="MHLLEXP2", resident_id=chloe.id, visitor_name="Mark Hill", valid_from=now - timedelta(days=2), valid_until=now - timedelta(days=1)),
            VisitorPass(code="LFRDREV2", resident_id=diego.id, visitor_name="Lena Ford", valid_from=now - timedelta(hours=1),
                        valid_until=now + timedelta(hours=3), revoked_at=now - timedelta(minutes=20))])

    if not EntryRequest.query.filter_by(visitor_name="Casey Wu").first():
        for name, unit, status, decider, ago in [("Casey Wu", "2A", "approved", aisha, 2), ("Tom Reed", "3A", "denied", chloe, 5), ("Ivy Chen", "5B", "pending", None, 26)]:
            created = now - timedelta(hours=ago)
            db.session.add(EntryRequest(token=secrets.token_urlsafe(16), visitor_name=name, unit_number=unit, status=status, created_at=created,
                                        expires_at=created + timedelta(minutes=2), decided_at=created + timedelta(minutes=1) if decider else None,
                                        decided_by=decider.id if decider else None))

    if not ParkingPermit.query.filter_by(code="PKBENC24").first():
        for resident, code, plate, visitor, hours, status, start, decider in [
                (ben, "PKBENC24", "CXRT 482", "Sam Lee", 4, "approved", now - timedelta(hours=1), priya),
                (aisha, "PKAYSH24", "BKLM 907", "Nora Patel", 24, "pending", now - timedelta(minutes=10), None),
                (emma, "PKEMMA24", "LMNP 351", "Ravi Shah", 2, "declined", now - timedelta(hours=3), lucas),
                (grace, "PKGRCE24", "QWRT 778", "Tara Moss", 2, "approved", now - timedelta(days=1), priya)]:
            db.session.add(ParkingPermit(resident_id=resident.id, code=code, plate=plate, plate_key=plate.replace(" ", ""), visitor_name=visitor,
                                         hours=hours, status=status, starts_at=start, ends_at=start + timedelta(hours=hours),
                                         decided_at=start if decider else None, decided_by=decider.id if decider else None))

    if not WatchlistEntry.query.filter_by(name_key="alex stone").first():
        db.session.add(WatchlistEntry(name="Alex Stone", name_key="alex stone", reason="Threatened front desk staff", added_by=maya.id,
                                      created_at=now - timedelta(days=3)))
        db.session.add(AuditLog(user_id=maya.id, performed_by=maya.id, action="watchlist_added", details="Alex Stone",
                                reason="Threatened front desk staff", timestamp=now - timedelta(days=3)))

def seed_front_desk(staff, keys):
    maya, daniel, priya, lucas = staff
    now = datetime.utcnow()

    if not Package.query.filter_by(description="Padded envelope").first():
        for unit, carrier, description, ago, released in [("2A", "Amazon", "Small box", 2, None), ("2A", "Canada Post", "Padded envelope", 1, None),
                                                          ("3B", "UPS", "Large box, heavy", 5, lucas), ("4A", "FedEx", "Documents", 3, None)]:
            db.session.add(Package(unit_number=unit, carrier=carrier, description=description, logged_by=priya.id, logged_at=now - timedelta(hours=ago),
                                   picked_up_at=now - timedelta(hours=1) if released else None, released_by=released.id if released else None))

    if not ShiftLogEntry.query.filter(ShiftLogEntry.body.like("Courier tried%")).first():
        db.session.add_all([
            ShiftLogEntry(author_id=lucas.id, category="Security", body="Courier tried to enter through the garage; sent to the front door.", created_at=now - timedelta(hours=26)),
            ShiftLogEntry(author_id=priya.id, category="Note", body="Lobby lights flickering near the mailboxes.", created_at=now - timedelta(hours=5)),
            ShiftLogEntry(author_id=priya.id, category="Maintenance", unit_number="4B", body="Plumber for 4B at 9 am, let them into the unit.",
                          is_handover=True, created_at=now - timedelta(hours=4))])

    if not KeyLoan.query.filter_by(contractor="Sam Ortiz").first():
        for key, contractor, company, purpose, out, due, returned in [
                ("Boiler Room", "Mike Ross", "CoolAir HVAC", "Boiler service", 1, -2, None),
                ("Roof Access", "Dana Lee", "Skyline Roofing", "Roof inspection", 3, 0.5, None),
                ("Electrical Room", "Sam Ortiz", "Volt Electric", "Panel check", 26, 24, lucas)]:
            db.session.add(KeyLoan(key_id=keys[key].id, contractor=contractor, company=company, purpose=purpose, signed_out_by=priya.id,
                                   signed_out_at=now - timedelta(hours=out), expected_return=now - timedelta(hours=due),
                                   returned_at=now - timedelta(hours=24) if returned else None, received_by=returned.id if returned else None))

    if not LostItem.query.filter_by(description="Blue water bottle").first():
        db.session.add_all([
            LostItem(description="Black umbrella", found_location="Lobby", notes="Found by the mailboxes", logged_by=priya.id, found_at=now - timedelta(hours=6)),
            LostItem(description="AirPods case", found_location="Gym", notes="Kept in the desk drawer", logged_by=lucas.id, found_at=now - timedelta(days=1)),
            LostItem(description="Blue water bottle", found_location="Rooftop", logged_by=priya.id, found_at=now - timedelta(days=2),
                     returned_at=now - timedelta(days=1), claimant_name="Ben Carter", returned_by=lucas.id)])


def seed_demo(password):
    zones = {name: get_or_create(Zone, {"name": name}, description=desc) for name, desc in ZONES.items()}
    main_door = get_or_create(Door, {"name": "Main Entrance"}, location="Lobby", door_type="main", is_active=True)
    main_door.zone_id = zones["Ground"].id
    common = {name: get_or_create(Door, {"name": name}, location=loc, door_type="common", is_active=True, zone_id=zones[zone].id)
              for name, loc, zone in COMMON_DOORS}
    unit_doors = {unit: get_or_create(Door, {"name": f"Unit {unit} Door"}, location=f"Floor {unit[:-1]}, Unit {unit}",
                                      door_type="unit", associated_unit=unit, is_active=True) for unit in UNITS}

    staff = [demo_user(role, first, last, password) for role, first, last in STAFF]
    residents = []
    for (first, last), unit in zip(RESIDENTS, UNITS):
        resident = demo_user("resident", first, last, password, unit_number=unit, floor=int(unit[:-1]),
                             door_id=unit_doors[unit].id, door_code=secrets.token_hex(8).upper())
        resident.zones = [zones["Ground"], zones["Gym"], zones["Amenities"]] + ([zones["Rooftop"]] if unit.startswith("6") else [])
        residents.append(resident)
    guest = demo_user("guest", "Oliver", "Grant", password, access_expires_at=datetime.utcnow() + timedelta(days=7))
    cleaner = demo_user("cleaner", "Rosa", "Diaz", password)
    cleaner.zones = list(zones.values())
    guest.zones = [zones["Ground"]]
    keys = {name: get_or_create(BuildingKey, {"name": name}, location=location) for name, location in BUILDING_KEYS}
    seed_visitors(staff, residents)
    seed_front_desk(staff, keys)

    created = [u for u in staff + residents + [guest, cleaner] if not AuditLog.query.filter_by(user_id=u.id, action="create").first()]
    for user in created:
        db.session.add(AuditLog(user_id=user.id, performed_by=staff[0].id, action="create",
                                details=f"User {user.username} created with role {user.role}"))

    demo_ids = [u.id for u in residents]
    if not AccessLog.query.filter(AccessLog.user_id.in_(demo_ids)).first():
        seed_history(residents, unit_doors, main_door, common["Gym Door"], guest, staff[2])
    db.session.commit()
    return {"created_users": len(created), "residents": len(residents), "staff": len(staff)}


if __name__ == "__main__":
    from app import create_app
    from config import Config
    if Config.APP_ENV == "production":
        sys.exit("Demo data is for development and classroom use only.")
    password = os.environ.get("DEMO_SEED_PASSWORD", "Demo@2026")
    with create_app().app_context():
        summary = seed_demo(password)
    print(f"Demo data ready ({summary['created_users']} new accounts). Password for every demo account: {password}")
    for role, first, last in STAFF + [("resident", *RESIDENTS[0]), ("guest", "Oliver", "Grant"), ("cleaner", "Rosa", "Diaz")]:
        print(f"  {role:<11} {first.lower()}.{last.lower()}@{DOMAIN}")
