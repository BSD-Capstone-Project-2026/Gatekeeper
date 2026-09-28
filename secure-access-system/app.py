# app.py
# Main application entry point

from flask import Flask
from flask_jwt_extended import JWTManager
from flask_login import LoginManager
from config import Config
from models import db, User, Door, Zone, AccessLog, AccessLogArchive
from routes.web import access_bp, web_bp
from routes.auth import auth_bp
from routes.users import users_bp
from routes.protected import protected_bp
from routes.dashboard import dashboard_bp
import secrets
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import subprocess

scheduler = BackgroundScheduler()


def archive_old_logs():
    cutoff = datetime.utcnow() - timedelta(days=90)   # adjust retention period
    old_logs = AccessLog.query.filter(AccessLog.timestamp < cutoff).all()

    for log in old_logs:
        archive = AccessLogArchive(
            user_id=log.user_id,
            door_id=log.door_id,
            timestamp=log.timestamp,
            success=log.success,
            failure_reason=log.failure_reason,
            wifi_verified=log.wifi_verified,
            proximity_verified=log.proximity_verified,
            ip_address=log.ip_address,
            user_agent=log.user_agent
        )
        db.session.add(archive)
        db.session.delete(log)

    db.session.commit()
    print(f"Archived {len(old_logs)} old access logs.")


def backup_task():
    subprocess.run(['python', 'scripts/backup.py'])


def create_app(config=Config):
    app = Flask(__name__, template_folder='templates')
    app.config.from_object(config)

    # Initialize Extensions
    db.init_app(app)
    JWTManager(app)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "web.login"

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(protected_bp)
    app.register_blueprint(web_bp)
    app.register_blueprint(access_bp)
    app.register_blueprint(dashboard_bp)

    # Database Setup + Seeding
    with app.app_context():
        db.create_all()
        if app.config.get("TESTING"):
            return app

        # ----- Users -----
        demo_user = User.query.filter_by(email=Config.DEMO_USER_EMAIL).first()
        if not demo_user:
            demo_user = User(
                first_name="Building",
                last_name="Management",
                username="building.management",
                email=Config.DEMO_USER_EMAIL,
                role="management"
            )
            demo_user.set_password(Config.DEMO_USER_PASSWORD)
            db.session.add(demo_user)
            print("✅ Demo management account created")

        backup_admin = User.query.filter_by(email="admin@backup.local").first()
        if not backup_admin:
            backup_admin = User(
                first_name="Backup",
                last_name="Admin",
                username="backup.admin",
                email="admin@backup.local",
                role="management"
            )
            backup_admin.set_password("BackupPass123")
            db.session.add(backup_admin)
            print("✅ Backup admin account created")

        # Test resident (navish.xx)
        test_resident = User.query.filter_by(email="resident@test.com").first()
        if not test_resident:
            test_resident = User(
                first_name="Navish",
                last_name="XX",
                username="navish.xx",
                email="resident@test.com",
                role="resident",
                unit_number="40A",
                floor=40,
                door_code=secrets.token_hex(8).upper()
            )
            test_resident.set_password("resident123")
            db.session.add(test_resident)
            print("✅ Test resident created")
        else:
            print("ℹ️ Test resident already exists")

        db.session.commit()

        # ----- Zones -----
        if Zone.query.count() == 0:
            gym = Zone(name="Gym", description="Fitness area")
            amenities = Zone(name="Amenities", description="Common amenities")
            ground = Zone(name="Ground", description="Ground floor")
            rooftop = Zone(name="Rooftop", description="Rooftop terrace")

            db.session.add_all([gym, amenities, ground, rooftop])
            db.session.commit()
            print("✅ Zones seeded")
        else:
            ground = Zone.query.filter_by(name="Ground").first()
            print("ℹ️ Zones already exist")

        # ----- Doors -----
        main_door = Door.query.filter_by(name="Main Entrance").first()

        if not main_door:
            main_door = Door(
                name="Main Entrance",
                location="Lobby",
                door_type="main",
                is_active=True
            )
            db.session.add(main_door)
            db.session.commit()
            print("✅ Main entrance door created")
        else:
            print("ℹ️ Main entrance door already exists")

        # Assign main door to Ground zone
        ground = Zone.query.filter_by(name="Ground").first()

        if ground and main_door.zone_id != ground.id:
            main_door.zone_id = ground.id
            db.session.commit()
            print("✅ Main entrance assigned to Ground zone")

        # Ensure all unit doors have no zone
        unit_doors = Door.query.filter_by(door_type="unit").all()

        for door in unit_doors:
            if door.zone_id is not None:
                door.zone_id = None

        if unit_doors:
            db.session.commit()
            print("✅ Unit doors cleared from zones")

        # Create unit doors for existing residents if missing
        residents = User.query.filter_by(role="resident").all()

        for resident in residents:

            if resident.door_id is None:

                existing_door = Door.query.filter_by(
                    associated_unit=resident.unit_number
                ).first()

                if existing_door:
                    resident.door_id = existing_door.id

                else:
                    door = Door(
                        name=f"Unit {resident.unit_number} Door",
                        location=f"Floor {resident.floor}, Unit {resident.unit_number}",
                        door_type="unit",
                        associated_unit=resident.unit_number,
                        is_active=True,
                        zone_id=None
                    )

                    db.session.add(door)
                    db.session.flush()

                    resident.door_id = door.id

                print(f"✅ Door created for resident {resident.username}")

        db.session.commit()

        # ----- Assign test resident to Ground zone -----
        if ground:
            resident = User.query.filter_by(email="resident@test.com").first()

            if resident and ground not in resident.zones:
                resident.zones.append(ground)
                db.session.commit()
                print("✅ Test resident assigned to Ground zone")
            else:
                print("ℹ️ Test resident already in Ground zone")

        # ----- Scheduler Jobs -----
        scheduler.add_job(func=archive_old_logs, trigger="interval", days=1)
        scheduler.add_job(func=backup_task, trigger="interval", days=1)

        if not scheduler.running:
            scheduler.start()

    # Root route
    @app.route("/")
    def home():
        return "Secure Access System – Phase 1 Step 1 Running"

    return app


if __name__ == "__main__":
    app = create_app()
    print(app.url_map)
    app.run(debug=True)