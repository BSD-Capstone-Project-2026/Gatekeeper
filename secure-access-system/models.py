from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import bcrypt
from flask_login import UserMixin

db = SQLAlchemy()

# Association table for users and zones (many-to-many)
user_zones = db.Table('user_zones',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('zone_id', db.Integer, db.ForeignKey('zones.id'), primary_key=True)
)

class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    role = db.Column(db.String(20), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
        # Link to the unit door (for residents)
    door_id = db.Column(db.Integer, db.ForeignKey('doors.id'), nullable=True)

    # Relationship
    unit_door = db.relationship('Door', foreign_keys=[door_id], uselist=False)

    # Login security fields
    failed_login_attempts = db.Column(db.Integer, default=0)
    is_locked = db.Column(db.Boolean, default=False)
    temporary_password = db.Column(db.String(100), nullable=True)

    # Door access fields
    unit_number = db.Column(db.String(10), nullable=True)
    floor = db.Column(db.Integer, nullable=True)
    door_code = db.Column(db.String(20), unique=True, nullable=True)

    # Password reset fields
    reset_token = db.Column(db.String(100), nullable=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)

    # Relationship to zones (many-to-many)
    zones = db.relationship('Zone', secondary=user_zones, backref=db.backref('users', lazy='dynamic'))

    def set_password(self, password):
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
        self.password_hash = hashed.decode()
        self.temporary_password = password

    def check_password(self, password):
        return bcrypt.checkpw(password.encode(), self.password_hash.encode())

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


class Zone(db.Model):
    __tablename__ = 'zones'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(200))

    # Relationship to doors (one-to-many)
    doors = db.relationship('Door', backref='zone', lazy=True)


class Door(db.Model):
    __tablename__ = 'doors'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(50))
    door_type = db.Column(db.String(20))   # 'main', 'unit', 'common', etc.
    associated_unit = db.Column(db.String(10), nullable=True)
    zone_id = db.Column(db.Integer, db.ForeignKey('zones.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)


class AccessLog(db.Model):
    __tablename__ = 'access_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    door_id = db.Column(db.Integer, db.ForeignKey('doors.id'))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    success = db.Column(db.Boolean)
    wifi_verified = db.Column(db.Boolean)
    proximity_verified = db.Column(db.Boolean)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(200))