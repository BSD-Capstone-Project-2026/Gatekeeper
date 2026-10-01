# routes/web.py
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session, flash, current_app
from models import db, User, Door, AccessLog, Zone, AuditLog
from datetime import datetime, timedelta
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
import secrets
import string
from routes.decorators import role_required
from collections import defaultdict
from datetime import datetime, timedelta
import re
import time
from datetime import datetime, timedelta
from models import Incident, Notification
from utils.notifications import notify, send_email
from utils.log_integrity import verify_log_chain

# Blueprint for access API (door/elevator)
access_bp = Blueprint('access', __name__, url_prefix='/api/access')
start_time = time.time()
web_bp = Blueprint("web", __name__)

class RateLimiter:
    def __init__(self, max_attempts=5, window_seconds=60, block_seconds=300):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.block_seconds = block_seconds
        self.attempts = defaultdict(list)  # key: user_id:door_id, value: list of timestamps

    def is_allowed(self, user_id, door_id):
        key = f"{user_id}:{door_id}"
        now = datetime.utcnow()
        # Remove old attempts outside the window
        self.attempts[key] = [ts for ts in self.attempts[key] if now - ts < timedelta(seconds=self.window_seconds)]
        if len(self.attempts[key]) >= self.max_attempts:
            # Check if block period has passed
            oldest = min(self.attempts[key])
            if now - oldest < timedelta(seconds=self.block_seconds):
                return False, f"Rate limit exceeded. Too many attempts. Try again later."
            else:
                # Reset after block period
                self.attempts[key] = []
        return True, None

    def record_attempt(self, user_id, door_id):
        key = f"{user_id}:{door_id}"
        self.attempts[key].append(datetime.utcnow())

# Create a global instance
rate_limiter = RateLimiter()

# Login required decorator (using sessions)
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('web.login'))
        return f(*args, **kwargs)
    return decorated_function

BACKGROUND_ENDPOINTS = {"web.health", "web.recent_logs", "static"}

@web_bp.before_app_request
def enforce_session_timeout():
    if 'user_id' not in session:
        return None
    now = time.time()
    if now - session.get('last_activity', now) > current_app.config["SESSION_TIMEOUT_MINUTES"] * 60:
        session.clear()
        if request.path.startswith('/api/'):
            return jsonify({"error": "Session expired"}), 401
        return redirect(url_for('web.login', expired=1))
    if request.endpoint not in BACKGROUND_ENDPOINTS:
        session['last_activity'] = now

def account_status_error(user):
    if not user.is_active:
        return "account inactive"
    if user.is_locked:
        return "account locked"
    return None

# Helper functions for password and username generation
def generate_password(length=10):
    chars = string.ascii_letters + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))

def generate_username(first_name, last_name):
    """Generate username as first.last"""
    base = f"{first_name.lower()}.{last_name.lower()}"
    username = base
    counter = 1
    while User.query.filter_by(username=username).first():
        username = f"{base}{counter}"
        counter += 1
    return username

@web_bp.route("/")
def home():
    return redirect(url_for("web.login"))

@web_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html", success="Password updated. Please log in." if request.args.get("reset") else None,
                               error="Session expired due to inactivity. Please log in again." if request.args.get("expired") else None)

    email = request.form.get("email")
    password = request.form.get("password")
    
    if not email or not password:
        return render_template("login.html", error="Email and password required")

    user = User.query.filter_by(email=email).first()

    if not user:
        return render_template("login.html", error="Invalid credentials")
    
    if not user.is_active:
        return render_template("login.html", error="Account is deactivated")
    
    if user.is_locked:
        return render_template("login.html", error="Account is locked. Contact management.")

    if not user.check_password(password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= 3:
            user.is_locked = True
        db.session.commit()
        return render_template("login.html", error="Invalid credentials")
    
    # Successful login
    user.failed_login_attempts = 0
    db.session.commit()
    
    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={"role": user.role}
    )
    
    session['user_id'] = user.id
    session['user_role'] = user.role
    session['user_name'] = f"{user.first_name} {user.last_name}"
    session['user_email'] = user.email
    session['jwt_token'] = access_token
    session['last_activity'] = time.time()

    return redirect(url_for("web.concierge_dashboard" if user.role == 'concierge' else "web.dashboard"))


@web_bp.route("/concierge")
@login_required
@role_required('management', 'concierge')
def concierge_dashboard():
    return render_template("concierge_dashboard.html")


@web_bp.route("/api/recent-logs")
@login_required
@role_required('management', 'concierge')
def recent_logs():
    query = db.session.query(AccessLog, User, Door).outerjoin(User, AccessLog.user_id == User.id).outerjoin(Door, AccessLog.door_id == Door.id)
    since = request.args.get('since')
    if since:
        try:
            query = query.filter(AccessLog.timestamp > datetime.fromisoformat(since.rstrip('Z')))
        except ValueError:
            return jsonify({"error": "Invalid 'since' timestamp"}), 400
    rows = query.order_by(AccessLog.timestamp.desc()).limit(50).all()
    return jsonify({
        "cursor": rows[0][0].timestamp.isoformat() + "Z" if rows else since or datetime.utcnow().isoformat() + "Z",
        "logs": [{
            "timestamp": log.timestamp.isoformat() + "Z",
            "user_name": f"{user.first_name} {user.last_name}" if user else "Unknown",
            "door_name": door.name if door else "Unknown",
            "success": bool(log.success),
            "failure_reason": log.failure_reason or ""
        } for log, user, door in rows]
    })

@web_bp.route("/dashboard")
@login_required
def dashboard():
    users = User.query.order_by(User.created_at.desc()).all() if session.get('user_role') in ('management', 'concierge') else []
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    locked_users = User.query.filter_by(is_locked=True).count()
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_users = User.query.filter(User.created_at >= week_ago).count()
    user_role = session.get('user_role', 'guest')
    user_name = session.get('user_name', 'User')

    return render_template(
        "dashboard.html",
        users=users,
        total_users=total_users,
        active_users=active_users,
        locked_users=locked_users,
        recent_users=recent_users,
        user_role=user_role,
        user_name=user_name
    )

# Add near the elevator endpoint in routes/web.py

@access_bp.route('/request', methods=['POST'])
@jwt_required()
def request_access():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    door_id = data.get('door_id')
    wifi_ssid = data.get('wifi_ssid')
    proximity = data.get('proximity', False)

    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    door = Door.query.get(door_id)
    if not door:
        return jsonify({"error": "Door not found"}), 404

    status_error = account_status_error(user)
    if status_error:
        db.session.add(AccessLog(user_id=user.id, door_id=door.id, success=False, failure_reason=status_error,
                                 ip_address=request.remote_addr, user_agent=request.headers.get('User-Agent')))
        db.session.commit()
        return jsonify({"error": "Access denied", "access_granted": False}), 403

    # Rate limiting check (before processing)
    allowed, message = rate_limiter.is_allowed(user.id, door.id)
    if not allowed:
        return jsonify({"error": message, "access_granted": False}), 429

    # Simulated Wi-Fi check
    BUILDING_WIFI = "Avengers-x"
    wifi_ok = (wifi_ssid == BUILDING_WIFI)

    # Simulated proximity
    proximity_ok = bool(proximity)

    # Determine if user is allowed by role/unit
    permission = False
    if door.door_type == 'main' and user.role in ['resident', 'concierge', 'management']:
        permission = True
    elif door.door_type == 'unit' and door.associated_unit == user.unit_number:
        permission = True
    elif door.door_type == 'common' and user.role in ['concierge', 'management']:
        permission = True

    # Zone check
    zone_ok = True
    if door.zone_id:
        user_zone_ids = [z.id for z in user.zones]
        if door.zone_id not in user_zone_ids:
            zone_ok = False

    # Final decision
    success = permission and wifi_ok and proximity_ok and zone_ok

    reasons = []
    if not success:
        if not permission:
            reasons.append("permission denied")
        if not wifi_ok:
            reasons.append("wifi mismatch")
        if not proximity_ok:
            reasons.append("proximity false")
        if not zone_ok:
            reasons.append("zone restriction")

    failure_reason = ", ".join(reasons)

    # Log the attempt
    log = AccessLog(
        user_id=user.id,
        door_id=door.id,
        success=success,
        wifi_verified=wifi_ok,
        failure_reason=failure_reason,
        proximity_verified=proximity_ok,
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent')
    )
    db.session.add(log)
    db.session.commit()

    # Record the attempt for rate limiting (after logging)
    rate_limiter.record_attempt(user.id, door.id)

    # Detect repeated failed attempts
    if not success:
        if door.door_type == 'unit' and door.associated_unit:
            unit = door.associated_unit
            threshold = current_app.config["INCIDENT_FAILURE_THRESHOLD"]
            window = current_app.config["INCIDENT_WINDOW_MINUTES"]
            since = datetime.utcnow() - timedelta(minutes=window)

            last_success = db.session.query(db.func.max(AccessLog.timestamp)).filter(
                AccessLog.door_id == door.id,
                AccessLog.success == True,
                AccessLog.timestamp >= since
            ).scalar()

            recent_failures = AccessLog.query.filter(
                AccessLog.door_id == door.id,
                AccessLog.success == False,
                AccessLog.timestamp > (last_success or since)
            ).order_by(AccessLog.timestamp.asc()).all()

            if len(recent_failures) >= threshold:
                existing = Incident.query.filter_by(
                    unit_number=unit,
                    door_id=door.id,
                    status='open'
                ).first()

                if existing:
                    existing.attempt_count += 1
                    existing.last_attempt_time = log.timestamp
                    db.session.commit()
                else:
                    incident = Incident(
                        unit_number=unit,
                        door_id=door.id,
                        incident_type='repeated_failed_attempts',
                        status='open',
                        trigger_rule=f'{threshold} failed attempts within {window} minutes',
                        attempt_count=len(recent_failures),
                        first_attempt_time=recent_failures[0].timestamp,
                        last_attempt_time=log.timestamp
                    )
                    db.session.add(incident)
                    db.session.commit()

                    resident = User.query.filter_by(
                        unit_number=unit,
                        role='resident'
                    ).first()

                    if resident:
                        notify(resident, "Security alert: repeated failed attempts on your unit",
                               f"Security alert ({incident.incident_type}): {incident.attempt_count} failed attempts on "
                               f"{door.name} (unit {unit}) at {incident.last_attempt_time:%Y-%m-%d %H:%M} UTC.", incident.id)

    # Final response
    if success:
        return jsonify({"message": "Door unlocked", "access_granted": True}), 200
    else:
        return jsonify({"error": "Access denied", "access_granted": False}), 403

@web_bp.route("/api/notifications")
@login_required
def get_notifications():
    user_id = session.get('user_id')
    notifs = Notification.query.filter_by(user_id=user_id).order_by(Notification.created_at.desc()).all()
    return jsonify([{
        'id': n.id,
        'message': n.message,
        'status': n.status,
        'created_at': n.created_at.isoformat()
    } for n in notifs])


@web_bp.route("/api/incidents/<int:incident_id>")
@login_required
@role_required('management')
def incident_detail(incident_id):
    incident = Incident.query.get_or_404(incident_id)
    logs = incident.get_related_logs()
    return jsonify({
        'id': incident.id,
        'unit_number': incident.unit_number,
        'door_id': incident.door_id,
        'incident_type': incident.incident_type,
        'status': incident.status,
        'trigger_rule': incident.trigger_rule,
        'attempt_count': incident.attempt_count,
        'first_attempt_time': incident.first_attempt_time.isoformat(),
        'last_attempt_time': incident.last_attempt_time.isoformat(),
        'created_at': incident.created_at.isoformat(),
        'events': [{
            'timestamp': log.timestamp.isoformat(),
            'success': log.success,
            'failure_reason': log.failure_reason,
            'wifi_verified': log.wifi_verified,
            'proximity_verified': log.proximity_verified
        } for log in logs]
    })

@web_bp.route("/incidents/<int:incident_id>")
@login_required
@role_required('management')
def incident_view(incident_id):
    incident = Incident.query.get_or_404(incident_id)
    logs = incident.get_related_logs()
    return render_template("incident_detail.html", incident=incident, logs=logs)

@web_bp.route("/incident-list")
@login_required
@role_required('management', 'concierge')
def incident_list():
    incidents = Incident.query.order_by(Incident.created_at.desc()).all()
    open_count = sum(1 for i in incidents if i.status == 'open')
    return render_template("incident_list.html", incidents=incidents, open_count=open_count)

@web_bp.route("/incidents/<int:incident_id>/acknowledge", methods=["POST"])
@login_required
@role_required('management', 'concierge')
def acknowledge_incident(incident_id):
    incident = Incident.query.get_or_404(incident_id)
    if incident.status == 'open':
        incident.status = 'acknowledged'
        incident.acknowledged_by = session['user_id']
        incident.acknowledged_at = datetime.utcnow()
        db.session.commit()
    return redirect(url_for("web.incident_list"))

@web_bp.route("/emergency-override", methods=["GET", "POST"])
@login_required
@role_required('management')
def emergency_override():
    doors = Door.query.all()
    if request.method == "GET":
        return render_template("emergency_override.html", doors=doors)

    door = Door.query.get(request.form.get("door_id", type=int) or 0)
    reason = (request.form.get("reason") or "").strip()
    if not door:
        return render_template("emergency_override.html", doors=doors, error="Select a valid door."), 400
    if not reason:
        return render_template("emergency_override.html", doors=doors, error="A reason is required for every override."), 400
    if request.form.get("confirm") != "yes":
        return render_template("emergency_override.html", doors=doors, error="You must confirm the override."), 400

    user = User.query.get(session['user_id'])
    if not user.check_password(request.form.get("password") or ""):
        db.session.add(AuditLog(user_id=user.id, performed_by=user.id, action="override_denied", door_id=door.id,
                                reason=reason, details="Re-authentication failed"))
        db.session.commit()
        return render_template("emergency_override.html", doors=doors, error="Password incorrect. Override refused."), 403

    db.session.add(AuditLog(user_id=user.id, performed_by=user.id, action="emergency_override", door_id=door.id,
                            reason=reason, details=f"Emergency override executed on door '{door.name}'"))
    db.session.commit()
    return render_template("emergency_override.html", doors=doors, success=f"Emergency override executed for door '{door.name}'.")

# API endpoints for dashboard
@web_bp.route("/api/dashboard/stats")
@login_required
@role_required('management', 'concierge')
def dashboard_stats():
    week_ago = datetime.utcnow() - timedelta(days=7)
    return jsonify({
        "total_users": User.query.count(),
        "active_users": User.query.filter_by(is_active=True).count(),
        "locked_users": User.query.filter_by(is_locked=True).count(),
        "recent_users": User.query.filter(User.created_at >= week_ago).count(),
        "management_count": User.query.filter_by(role="management").count(),
        "concierge_count": User.query.filter_by(role="concierge").count(),
        "resident_count": User.query.filter_by(role="resident").count()
    })

@web_bp.route("/api/dashboard/recent-users")
@login_required
@role_required('management', 'concierge')
def recent_users_api():
    users = User.query.order_by(User.created_at.desc()).limit(5).all()
    result = []
    for user in users:
        if user.is_locked:
            status = "locked"
        elif not user.is_active:
            status = "inactive"
        else:
            status = "active"
        result.append({
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "status": status,
            "created": user.created_at.strftime("%Y-%m-%d") if user.created_at else "N/A"
        })
    return jsonify({"users": result})

@web_bp.route("/users")
@login_required
@role_required('management', 'concierge')
def users_list():
    query = User.query if session['user_role'] == 'management' else User.query.filter_by(role='resident')
    return render_template("users.html", users=query.all())

@web_bp.route("/users/toggle/<int:user_id>", methods=["POST"])
@login_required
@role_required('management')
def toggle_user(user_id):
    user = User.query.get_or_404(user_id)

    user.is_active = not user.is_active
    if user.is_active:
        user.is_locked = False
        user.failed_login_attempts = 0

    db.session.commit()
    # Audit log
    action = "activate" if user.is_active else "deactivate"
    audit = AuditLog(
        user_id=user.id,
        action=action,
        details=f"User {user.username} toggled active status",
        performed_by=session.get('user_id')
        )
    db.session.add(audit)
    db.session.commit()
    return redirect(url_for("web.users_list"))




@web_bp.route("/doors")
@login_required
@role_required('management')
def list_doors():
    doors = Door.query.all()
    zones = Zone.query.all()
    return render_template("doors.html", doors=doors, zones=zones)



@web_bp.route("/create-user", methods=["GET", "POST"])
@login_required
@role_required('management', 'concierge')
def create_user():
    current_user_role = session.get('user_role')
    allowed_roles = ['resident'] if current_user_role == 'concierge' else ['concierge', 'resident']

    if request.method == "GET":
        return render_template("create_user.html", allowed_roles=allowed_roles)

    # ---------------------------
    # Handle POST
    # ---------------------------
    first_name = request.form.get("first_name")
    last_name = request.form.get("last_name")
    email = request.form.get("email")
    role = request.form.get("role")

    if not all([first_name, last_name, email, role]):
        return render_template("create_user.html", error="All fields required", allowed_roles=allowed_roles)

    if User.query.filter_by(email=email).first():
        return render_template("create_user.html", error="User already exists", allowed_roles=allowed_roles)

    if current_user_role == 'concierge' and role != 'resident':
        return render_template(
            "create_user.html",
            error="Concierge can only create resident accounts",
            allowed_roles=['resident']
        )

    password = generate_password()
    username = generate_username(first_name, last_name)

    unit_number = None
    floor = None
    door_code = None
    unit_door = None

    # ---------------------------
    # Resident logic
    # ---------------------------
    if role == 'resident':
        unit_number = request.form.get("unit_number")
        if not unit_number:
            return render_template(
                "create_user.html",
                error="Unit number is required for residents",
                allowed_roles=allowed_roles
            )

        match = re.match(r"^(\d+)", unit_number)
        floor = int(match.group(1)) if match else 1
        door_code = secrets.token_hex(8).upper()

        # Create unit door
        unit_door = Door(
            name=f"Unit {unit_number} Door",
            location=f"Floor {floor}, Unit {unit_number}",
            door_type="unit",
            associated_unit=unit_number,
            is_active=True
        )
        db.session.add(unit_door)
        db.session.flush()  # ✅ get unit_door.id before commit

    # ---------------------------
    # Create user
    # ---------------------------
    user = User(
        first_name=first_name,
        last_name=last_name,
        username=username,
        email=email,
        role=role,
        unit_number=unit_number,
        floor=floor,
        door_code=door_code,
        door_id=unit_door.id if unit_door else None
    )
    user.set_password(password)

    db.session.add(user)
    db.session.flush()
    # After successful user creation, add:
    audit = AuditLog(
    user_id=user.id,
    action='create',
    details=f"User {user.username} created with role {user.role}",
    performed_by=session.get('user_id')
    )
    db.session.add(audit)
    db.session.commit()

    user_data = {
        "username": username,
        "email": email,
        "role": role,
        "temp_password": password,
        "unit_number": unit_number,
        "door_code": door_code,
        "floor": floor
    }

    return render_template(
        "create_user.html",
        success=True,
        user_data=user_data,
        allowed_roles=allowed_roles
    )
@web_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "GET":
        return render_template("forgot_password.html")
    
    email = request.form.get("email")
    user = User.query.filter_by(email=email).first()

    if user:
        user.reset_token = secrets.token_urlsafe(32)
        user.reset_token_expiry = datetime.utcnow() + timedelta(hours=1)
        db.session.commit()
        link = url_for("web.reset_password_with_token", token=user.reset_token, _external=True)
        if send_email(user.email, "Gatekeeper password reset", f"Reset your password within 1 hour: {link}") is None:
            current_app.logger.info("Password reset link for %s: %s", user.email, link)

    return render_template("forgot_password.html", success="If an account exists for that email, a reset link has been sent.")

@web_bp.route("/logs/verify")
@login_required
@role_required('management')
def verify_logs():
    return jsonify(verify_log_chain())

@web_bp.route("/audit")
@login_required
@role_required('management')
def audit_logs():
    action = request.args.get('action')
    query = AuditLog.query.filter_by(action=action) if action else AuditLog.query
    actions = [a for (a,) in db.session.query(AuditLog.action).distinct().order_by(AuditLog.action)]
    return render_template("audit_logs.html", logs=query.order_by(AuditLog.timestamp.desc()).all(), actions=actions, action=action)

@web_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password_with_token(token):
    user = User.query.filter_by(reset_token=token).first()
    
    if not user or not user.reset_token_expiry or user.reset_token_expiry < datetime.utcnow():
        return render_template("reset_with_token.html", invalid=True)

    if request.method == "GET":
        return render_template("reset_with_token.html", token=token)

    new_password = request.form.get("new_password") or ""
    if len(new_password) < 8:
        return render_template("reset_with_token.html", token=token, error="Password must be at least 8 characters")
    if new_password != request.form.get("confirm_password"):
        return render_template("reset_with_token.html", token=token, error="Passwords do not match")
    user.set_password(new_password)
    user.reset_token = None
    user.reset_token_expiry = None
    db.session.commit()
    return redirect(url_for("web.login", reset=1))



@web_bp.route("/simulate")
@login_required
@role_required('resident')
def simulate():
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    if not user:
        return redirect(url_for('web.logout'))

    main_door = Door.query.filter_by(door_type='main').first()
    main_door_id = main_door.id if main_door else None

    return render_template(
        "simulate.html",
        unit=user.unit_number,
        floor=user.floor,
        door_code=user.door_code,
        unit_door_id=user.door_id,          # from the user's door relation
        main_door_id=main_door_id,
        jwt_token=session.get("jwt_token")
    )

@access_bp.route('/elevator/call', methods=['POST'])
@jwt_required()
def call_elevator():
    user = User.query.get(get_jwt_identity())
    if not user:
        return jsonify({"error": "User not found"}), 404
    if account_status_error(user):
        return jsonify({"error": "Access denied"}), 403
    if user.role != 'resident':
        return jsonify({"error": "Only residents can use elevator"}), 403
    return jsonify({"message": "Elevator summoned", "floor": user.floor}), 200

# (Add more access endpoints as needed, e.g., door unlock)

@web_bp.route("/profile")
@login_required
def profile():
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    if not user:
        session.clear()
        return redirect(url_for('web.login'))
    notifications = Notification.query.filter_by(user_id=user.id).order_by(Notification.created_at.desc()).all()
    unread = sum(1 for n in notifications if not n.is_read)
    page = render_template("profile.html", user=user, notifications=notifications, unread=unread)
    Notification.query.filter_by(user_id=user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return page

@web_bp.route("/reset-password", methods=["GET", "POST"])
@login_required
def reset_password():
    if request.method == "GET":
        return render_template("reset_password.html")
    
    current_password = request.form.get("current_password")
    new_password = request.form.get("new_password")
    confirm_password = request.form.get("confirm_password")
    
    if not all([current_password, new_password, confirm_password]):
        return render_template("reset_password.html", error="All fields are required")
    
    if new_password != confirm_password:
        return render_template("reset_password.html", error="New passwords don't match")
    
    if len(new_password) < 6:
        return render_template("reset_password.html", error="Password must be at least 6 characters")
    
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    
    if not user.check_password(current_password):
        return render_template("reset_password.html", error="Current password is incorrect")
    
    user.set_password(new_password)
    db.session.commit()
    
    return render_template("reset_password.html", success="Password updated successfully!")



from sqlalchemy import text   # add this import at the top

@web_bp.route('/health')
def health():
    db_status = 'healthy'
    try:
        db.session.execute(text('SELECT 1')).scalar()   # wrap with text()
    except Exception as e:
        db_status = 'unhealthy'
        print("="*50)
        print("❌ Database health check failed!")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {e}")
        print("="*50)
    return jsonify({'server': 'healthy', 'database': db_status, 'network': 'healthy'})


@web_bp.route("/unlock-user/<int:user_id>", methods=["POST"])
@login_required
@role_required('management')
def unlock_user(user_id):
    user = User.query.get(user_id)
    if user:
        user.is_locked = False
        user.failed_login_attempts = 0
        db.session.commit()
        audit = AuditLog(
            user_id=user.id,
            action='unlock',
            details=f"User {user.username} unlocked",
            performed_by=session.get('user_id')
        )
        db.session.add(audit)
        db.session.commit()
    return redirect(url_for("web.users_list"))

@web_bp.route("/incidents")
@login_required
@role_required('management')
def incidents():
    # Get date filters from query string (optional)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    door_id = request.args.get('door_id', type=int)
    errors = []

    query = db.session.query(AccessLog, User, Door).outerjoin(User, AccessLog.user_id == User.id).outerjoin(Door, AccessLog.door_id == Door.id)

    if start_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(AccessLog.timestamp >= start)
        except ValueError:
            errors.append("Invalid start date format. Use YYYY-MM-DD.")

    if end_date:
        try:
            end = datetime.strptime(end_date + ' 23:59:59', '%Y-%m-%d %H:%M:%S')
            query = query.filter(AccessLog.timestamp <= end)
        except ValueError:
            errors.append("Invalid end date format. Use YYYY-MM-DD.")

    if door_id:
        query = query.filter(AccessLog.door_id == door_id)

    logs = []
    for log, user, door in query.order_by(AccessLog.timestamp.desc()).all():
        logs.append(log)
        log.user_name = f"{user.first_name} {user.last_name}" if user else "Unknown"
        log.door_name = door.name if door else "Unknown"
        log.reason = []
        if not log.wifi_verified:
            log.reason.append("Wi‑Fi mismatch")
        if not log.proximity_verified:
            log.reason.append("proximity false")
        if log.success is False and log.wifi_verified and log.proximity_verified:
            log.reason.append("permission denied")
        log.reason_str = ", ".join(log.reason) if log.reason else "Success"

    return render_template("incidents.html", logs=logs, start_date=start_date, end_date=end_date,
                           door_id=door_id, doors=Door.query.order_by(Door.name).all(), errors=errors)


@web_bp.route("/profile/incidents")
@login_required
def my_incidents():
    user_id = session.get("user_id")
    logs = AccessLog.query.filter_by(user_id=user_id)\
        .order_by(AccessLog.timestamp.desc())\
        .all()

    for log in logs:
        door = Door.query.get(log.door_id)
        log.door_name = door.name if door else "Unknown"
        log.reason = []
        if not log.wifi_verified:
            log.reason.append("Wi-Fi mismatch")
        if not log.proximity_verified:
            log.reason.append("proximity false")
        if not log.success and log.wifi_verified and log.proximity_verified:
            log.reason.append("permission denied")
        log.reason_str = ", ".join(log.reason) if log.reason else "Success"

    return render_template("my_incidents.html", logs=logs)
@web_bp.route("/zones")
@login_required
@role_required('management')
def list_zones():
    zones = Zone.query.all()
    return render_template("zones.html", zones=zones)

@web_bp.route("/zones/create", methods=["GET", "POST"])
@login_required
@role_required('management')
def create_zone():
    if request.method == "GET":
        return render_template("zone_form.html")

    name = request.form.get("name")
    description = request.form.get("description")
    if not name:
        return render_template("zone_form.html", error="Zone name is required")

    zone = Zone(name=name, description=description)
    db.session.add(zone)
    db.session.commit()
    return redirect(url_for("web.list_zones"))

@web_bp.route("/zones/<int:zone_id>/edit", methods=["GET", "POST"])
@login_required
@role_required('management')
def edit_zone(zone_id):
    zone = Zone.query.get_or_404(zone_id)
    if request.method == "GET":
        return render_template("zone_form.html", zone=zone)

    zone.name = request.form.get("name")
    zone.description = request.form.get("description")
    db.session.commit()
    return redirect(url_for("web.list_zones"))

@web_bp.route("/zones/<int:zone_id>/delete", methods=["POST"])
@login_required
@role_required('management')
def delete_zone(zone_id):
    zone = Zone.query.get_or_404(zone_id)
    # Check if any doors use this zone
    if zone.doors:
        return render_template("error.html", error="Cannot delete zone with assigned doors.")
    db.session.delete(zone)
    db.session.commit()
    return redirect(url_for("web.list_zones"))

@web_bp.route("/doors/<int:door_id>/assign_zone", methods=["POST"])
@login_required
@role_required('management')
def assign_door_zone(door_id):
    door = Door.query.get_or_404(door_id)
    zone_id = request.form.get("zone_id")
    if zone_id:
        door.zone_id = int(zone_id)
    else:
        door.zone_id = None
    db.session.commit()
    return redirect(url_for("web.list_doors"))  # we'll need a door list page

@web_bp.route("/users/<int:user_id>/zones", methods=["GET", "POST"])
@login_required
@role_required('management')
def manage_user_zones(user_id):
    user = User.query.get_or_404(user_id)
    zones = Zone.query.all()
    if request.method == "GET":
        return render_template("user_zones.html", user=user, zones=zones)

    # Update zones: form sends list of zone_ids
    selected_zone_ids = request.form.getlist("zone_ids")  # list of strings
    user.zones = [Zone.query.get(int(zid)) for zid in selected_zone_ids]
    db.session.commit()
    return redirect(url_for("web.users_list"))

@web_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("web.login"))