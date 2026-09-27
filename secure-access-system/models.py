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
    door_id = db.Column(db.Integer, db.ForeignKey('doors.id'), nullable=True)
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

class Incident(db.Model):
    __tablename__ = 'incidents'

    id = db.Column(db.Integer, primary_key=True)
    unit_number = db.Column(db.String(10), nullable=False)
    door_id = db.Column(db.Integer, db.ForeignKey('doors.id'))
    incident_type = db.Column(db.String(50))
    status = db.Column(db.String(20), default='open')
    trigger_rule = db.Column(db.String(200))
    attempt_count = db.Column(db.Integer)
    first_attempt_time = db.Column(db.DateTime)
    last_attempt_time = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)

    door = db.relationship('Door')

    def get_related_logs(self):
        return AccessLog.query.filter(
            AccessLog.door_id == self.door_id,
            AccessLog.success == False,
            AccessLog.timestamp >= self.first_attempt_time,
            AccessLog.timestamp <= self.last_attempt_time
        ).order_by(AccessLog.timestamp.asc()).all()
    door = db.relationship('Door')
    def get_related_logs(self):
        # Get failed attempts for this door within the time window
         return AccessLog.query.filter(
            AccessLog.door_id == self.door_id,
            AccessLog.success == False,
            AccessLog.timestamp >= self.first_attempt_time,
            AccessLog.timestamp <= self.last_attempt_time
        ).order_by(AccessLog.timestamp.asc()).all()

class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    incident_id = db.Column(db.Integer, db.ForeignKey('incidents.id'), nullable=True)
    message = db.Column(db.String(500))
    status = db.Column(db.String(20), default='queued')  # queued, sent, failed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sent_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User', backref='notifications')


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
    failure_reason = db.Column(db.String(100), nullable=True) 
    wifi_verified = db.Column(db.Boolean)
    proximity_verified = db.Column(db.Boolean)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(200))

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(50), nullable=False)        
    details = db.Column(db.String(200))
    reason = db.Column(db.String(200), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    performed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

class AccessLogArchive(db.Model):
    __tablename__ = 'access_logs_archive'
    id = db.Column(db.Integer, primary_key=True)
    door_id = db.Column(db.Integer, db.ForeignKey('doors.id'), nullable=True)
    unit_door = db.relationship('Door', foreign_keys=[door_id], uselist=False)
    timestamp = db.Column(db.DateTime)
    success = db.Column(db.Boolean)
    failure_reason = db.Column(db.String(100))
    wifi_verified = db.Column(db.Boolean)
    proximity_verified = db.Column(db.Boolean)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(200))