from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session
import bcrypt
import hashlib
from flask_login import UserMixin
from utils.encryption import encrypt, decrypt

db = SQLAlchemy()


def add_missing_columns():
    inspector = db.inspect(db.engine)
    for table in db.metadata.sorted_tables:
        existing = {c["name"] for c in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name not in existing:
                default = column.default.arg if column.default is not None and column.default.is_scalar else None
                suffix = "" if default is None else f" DEFAULT {int(default) if isinstance(default, bool) else repr(default)}"
                db.session.execute(db.text(f"ALTER TABLE {table.name} ADD COLUMN {column.name} {column.type.compile(db.engine.dialect)}{suffix}"))
    db.session.commit()

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
    access_expires_at = db.Column(db.DateTime, nullable=True)

    # Login security fields
    failed_login_attempts = db.Column(db.Integer, default=0)
    is_locked = db.Column(db.Boolean, default=False)
    temporary_password = db.Column(db.String(100), nullable=True)

    # Door access fields
    unit_number = db.Column(db.String(10), nullable=True)
    floor = db.Column(db.Integer, nullable=True)
    _door_code = db.Column("door_code", db.String(200), unique=True, nullable=True)

    # Password reset fields
    reset_token = db.Column(db.String(100), nullable=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)

    # Relationship to zones (many-to-many)
    zones = db.relationship('Zone', secondary=user_zones, backref=db.backref('users', lazy='dynamic'))

    @property
    def door_code(self):
        return decrypt(self._door_code) if self._door_code else None

    @door_code.setter
    def door_code(self, value):
        self._door_code = encrypt(value) if value else None

    def set_password(self, password):
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
        self.password_hash = hashed.decode()

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
    acknowledged_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    acknowledged_at = db.Column(db.DateTime, nullable=True)

    door = db.relationship('Door')
    acknowledger = db.relationship('User', foreign_keys=[acknowledged_by])

    def get_related_logs(self):
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
    is_read = db.Column(db.Boolean, default=False)

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
    is_locked = db.Column(db.Boolean, default=True)


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
    visitor_name = db.Column(db.String(80), nullable=True)
    prev_hash = db.Column(db.String(64))
    row_hash = db.Column(db.String(64))

    def compute_hash(self):
        fields = [self.user_id, self.door_id, self.timestamp.isoformat(), self.success, self.failure_reason,
                  self.wifi_verified, self.proximity_verified, self.ip_address, self.user_agent, self.prev_hash]
        if self.visitor_name:
            fields.append(self.visitor_name)
        return hashlib.sha256("|".join(map(str, fields)).encode()).hexdigest()


def seal_logs(logs, prev_hash):
    for log in logs:
        log.timestamp = log.timestamp or datetime.utcnow()
        log.prev_hash = prev_hash
        log.row_hash = prev_hash = log.compute_hash()


@event.listens_for(Session, "before_flush")
def seal_new_access_logs(session, flush_context, instances):
    new_logs = sorted((o for o in session.new if isinstance(o, AccessLog)), key=lambda o: inspect(o).insert_order)
    if new_logs:
        last = session.execute(db.select(AccessLog.row_hash).order_by(AccessLog.id.desc()).limit(1)).scalar()
        seal_logs(new_logs, last)


def seal_existing_logs():
    if AccessLog.query.filter(AccessLog.row_hash.isnot(None)).first():
        return 0
    logs = AccessLog.query.order_by(AccessLog.id).all()
    seal_logs(logs, None)
    db.session.commit()
    return len(logs)

class RateLimitBlock(db.Model):
    __tablename__ = 'rate_limit_blocks'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    door_id = db.Column(db.Integer, db.ForeignKey('doors.id'), nullable=False)
    blocked_until = db.Column(db.DateTime, nullable=False)

class VisitorPass(db.Model):
    __tablename__ = 'visitor_passes'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(12), unique=True, nullable=False)
    resident_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    visitor_name = db.Column(db.String(80), nullable=False)
    valid_from = db.Column(db.DateTime, nullable=False)
    valid_until = db.Column(db.DateTime, nullable=False)
    revoked_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    checked_in_at = db.Column(db.DateTime, nullable=True)
    checked_in_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    resident = db.relationship('User', foreign_keys=[resident_id])

    @property
    def status(self):
        now = datetime.utcnow()
        if self.revoked_at:
            return "Revoked"
        if now > self.valid_until:
            return "Expired"
        if now < self.valid_from:
            return "Scheduled"
        return "Checked in" if self.checked_in_at else "Active"

class EntryRequest(db.Model):
    __tablename__ = 'entry_requests'

    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(32), unique=True, nullable=False)
    visitor_name = db.Column(db.String(80), nullable=False)
    unit_number = db.Column(db.String(10), nullable=False)
    status = db.Column(db.String(10), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    decided_at = db.Column(db.DateTime, nullable=True)
    decided_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    decider = db.relationship('User')

    @property
    def current_status(self):
        if self.status == 'pending' and datetime.utcnow() > self.expires_at:
            return 'expired'
        return self.status

    @property
    def seconds_left(self):
        return max(0, int((self.expires_at - datetime.utcnow()).total_seconds()))

class ParkingPermit(db.Model):
    __tablename__ = 'parking_permits'

    id = db.Column(db.Integer, primary_key=True)
    resident_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    plate = db.Column(db.String(12), nullable=False)
    plate_key = db.Column(db.String(12), nullable=False, index=True)
    starts_at = db.Column(db.DateTime, default=datetime.utcnow)
    ends_at = db.Column(db.DateTime, nullable=False)
    code = db.Column(db.String(12), unique=True, nullable=True)
    visitor_name = db.Column(db.String(80), nullable=True)
    hours = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(10), default='pending')
    decided_at = db.Column(db.DateTime, nullable=True)
    decided_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    resident = db.relationship('User', foreign_keys=[resident_id])

    @property
    def current_status(self):
        if self.status == 'declined':
            return 'declined'
        if datetime.utcnow() >= self.ends_at:
            return 'expired' if self.status == 'approved' else 'lapsed'
        return 'active' if self.status == 'approved' else 'pending'

    @property
    def is_active(self):
        return self.current_status == 'active'

    @property
    def minutes_left(self):
        return max(0, int((self.ends_at - datetime.utcnow()).total_seconds() // 60))

class WatchlistEntry(db.Model):
    __tablename__ = 'watchlist_entries'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    name_key = db.Column(db.String(80), unique=True, nullable=False)
    reason = db.Column(db.String(200), nullable=False)
    added_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    adder = db.relationship('User')

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(50), nullable=False)        
    details = db.Column(db.String(200))
    reason = db.Column(db.String(200), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    performed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    door_id = db.Column(db.Integer, db.ForeignKey('doors.id'), nullable=True)

    performer = db.relationship('User', foreign_keys=[performed_by])
    door = db.relationship('Door')

class AccessLogArchive(db.Model):
    __tablename__ = 'access_logs_archive'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    door_id = db.Column(db.Integer, db.ForeignKey('doors.id'), nullable=True)
    unit_door = db.relationship('Door', foreign_keys=[door_id], uselist=False)
    timestamp = db.Column(db.DateTime)
    success = db.Column(db.Boolean)
    failure_reason = db.Column(db.String(100))
    wifi_verified = db.Column(db.Boolean)
    proximity_verified = db.Column(db.Boolean)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(200))