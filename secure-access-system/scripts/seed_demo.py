import os
import secrets
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db, User, Door, Zone, AccessLog, Incident, Notification, AuditLog

DOMAIN = "gatekeeper.demo"
STAFF = [("management", "Maya", "Chen"), ("management", "Daniel", "Okafor"),
         ("concierge", "Priya", "Sharma"), ("concierge", "Lucas", "Martin")]
RESIDENTS = [("Aisha", "Khan"), ("Ben", "Carter"), ("Chloe", "Nguyen"), ("Diego", "Ramirez"), ("Emma", "Wilson"),
             ("Farhan", "Ali"), ("Grace", "Kim"), ("Hiro", "Tanaka"), ("Isabel", "Rossi"), ("Jamal", "Brooks")]
UNITS = [f"{floor}{letter}" for floor in range(2, 7) for letter in "AB"]
ZONES = {"Ground": "Ground floor", "Gym": "Fitness area", "Amenities": "Common amenities", "Rooftop": "Rooftop terrace"}
COMMON_DOORS = [("Gym Door", "Level 1", "Gym"), ("Amenities Room Door", "Level 1", "Amenities"), ("Rooftop Door", "Roof", "Rooftop")]


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
