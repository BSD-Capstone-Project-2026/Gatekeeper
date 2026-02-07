# routes/web.py
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session
from models import db, User
from datetime import datetime, timedelta
from flask_jwt_extended import create_access_token
import secrets
import string

web_bp = Blueprint("web", __name__)

# Login required decorator (using sessions, not Flask-Login)
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('web.login'))
        return f(*args, **kwargs)
    return decorated_function

# Helper functions for password and username generation
def generate_password(length=10):
    chars = string.ascii_letters + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))

def generate_username(first_name, last_name):
    """Generate username as first.last"""
    base = f"{first_name.lower()}.{last_name.lower()}"
    username = base
    
    # Check if username exists, add number if it does
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
        return render_template("login.html")

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

    # Check password
    if not user.check_password(password):
        # Increment failed attempts
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= 3:
            user.is_locked = True
        db.session.commit()
        return render_template("login.html", error="Invalid credentials")
    
    # SUCCESSFUL LOGIN
    user.failed_login_attempts = 0
    db.session.commit()
    
    # Create JWT token (for API if needed)
    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={"role": user.role}
    )
    
    # Store user info in session (OUR method, not Flask-Login)
    session['user_id'] = user.id
    session['user_role'] = user.role
    session['user_name'] = f"{user.first_name} {user.last_name}"
    session['user_email'] = user.email
    session['jwt_token'] = access_token
    
    return redirect(url_for("web.dashboard"))


@web_bp.route("/dashboard")
@login_required
def dashboard():
    users = User.query.order_by(User.created_at.desc()).all()

    # Initial values (page loads instantly, JS updates later)
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    locked_users = User.query.filter_by(is_locked=True).count()

    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_users = User.query.filter(User.created_at >= week_ago).count()
    
    # Get current user role for display
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


# ---------------- API ENDPOINTS ----------------

@web_bp.route("/api/dashboard/stats")
@login_required
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
def users_list():
    users = User.query.all()
    return render_template("users.html", users=users)


@web_bp.route("/users/toggle/<int:user_id>")
@login_required
def toggle_user(user_id):  # CHANGED FROM toggle_user_activation
    user = User.query.get_or_404(user_id)
    
    # Check if current user has permission (only management)
    current_user_role = session.get('user_role')
    if current_user_role != 'management':
        return render_template("error.html", 
                             error="Only management can activate/deactivate users")
    
    # Toggle active status
    user.is_active = not user.is_active

    # If activating user, unlock them
    if user.is_active:
        user.is_locked = False
        user.failed_login_attempts = 0

    db.session.commit()
    return redirect(url_for("web.users_list"))


@web_bp.route("/create-user", methods=["GET", "POST"])
@login_required
def create_user():
    # Get current user's role from session
    current_user_role = session.get('user_role')
    
    # Check permissions
    if current_user_role not in ['management', 'concierge']:
        return render_template("error.html", 
                             error="You don't have permission to create users")

    if request.method == "GET":
        # Determine allowed roles based on current user's role
        allowed_roles = ['resident'] if current_user_role == 'concierge' else ['concierge', 'resident']
        return render_template("create_user.html", allowed_roles=allowed_roles)

    # Handle POST request
    first_name = request.form.get("first_name")
    last_name = request.form.get("last_name")
    email = request.form.get("email")
    role = request.form.get("role")

    # Validate inputs
    if not all([first_name, last_name, email, role]):
        allowed_roles = ['resident'] if current_user_role == 'concierge' else ['concierge', 'resident']
        return render_template("create_user.html", 
                             error="All fields required",
                             allowed_roles=allowed_roles)

    # Check if user already exists
    if User.query.filter_by(email=email).first():
        allowed_roles = ['resident'] if current_user_role == 'concierge' else ['concierge', 'resident']
        return render_template("create_user.html", 
                             error="User already exists",
                             allowed_roles=allowed_roles)
    
    # Enforce role permissions
    if current_user_role == 'concierge' and role != 'resident':
        return render_template("create_user.html", 
                             error="Concierge can only create resident accounts",
                             allowed_roles=['resident'])

    # Generate credentials
    password = generate_password()
    username = generate_username(first_name, last_name)

    # Create new user
    user = User(
        first_name=first_name,
        last_name=last_name,
        username=username,
        email=email,
        role=role
    )
    user.set_password(password)

    db.session.add(user)
    db.session.commit()

    # Show success with credentials
    allowed_roles = ['resident'] if current_user_role == 'concierge' else ['concierge', 'resident']
    return render_template(
        "create_user.html",
        success=True,
        user_data={
            "username": username,
            "email": email,
            "role": role,
            "temp_password": password
        },
        allowed_roles=allowed_roles
    )

@web_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "GET":
        return render_template("forgot_password.html")
    
    email = request.form.get("email")
    user = User.query.filter_by(email=email).first()
    
    if not user:
        return render_template("forgot_password.html", 
                             error="No account found with that email")
    
    # Generate reset token (simplified)
    reset_token = secrets.token_urlsafe(32)
    user.reset_token = reset_token
    user.reset_token_expiry = datetime.utcnow() + timedelta(hours=1)
    db.session.commit()
    
    # In real app: Send email with reset link
    # For now, just show token
    return render_template("forgot_password.html",
                         success=f"Reset token: {reset_token}")

@web_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password_with_token(token):
    user = User.query.filter_by(reset_token=token).first()
    
    if not user or user.reset_token_expiry < datetime.utcnow():
        return render_template("error.html", 
                             error="Invalid or expired reset token")
    
    if request.method == "GET":
        return render_template("reset_with_token.html", token=token)
    
    # ... handle password reset ...

@web_bp.route("/profile")
@login_required
def profile():
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    
    if not user:
        session.clear()
        return redirect(url_for('web.login'))
    
    return render_template("profile.html", user=user)


@web_bp.route("/reset-password", methods=["GET", "POST"])
@login_required
def reset_password():
    if request.method == "GET":
        return render_template("reset_password.html")
    
    current_password = request.form.get("current_password")
    new_password = request.form.get("new_password")
    confirm_password = request.form.get("confirm_password")
    
    if not all([current_password, new_password, confirm_password]):
        return render_template("reset_password.html", 
                             error="All fields are required")
    
    if new_password != confirm_password:
        return render_template("reset_password.html", 
                             error="New passwords don't match")
    
    if len(new_password) < 6:
        return render_template("reset_password.html", 
                             error="Password must be at least 6 characters")
    
    # Get current user
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    
    # Check current password
    if not user.check_password(current_password):
        return render_template("reset_password.html", 
                             error="Current password is incorrect")
    
    # Update password
    user.set_password(new_password)
    user.temporary_password = None  # Clear temporary password
    db.session.commit()
    
    return render_template("reset_password.html", 
                         success="Password updated successfully!")


@web_bp.route("/unlock-user/<int:user_id>")
@login_required
def unlock_user(user_id):
    # Check if current user has permission (only management)
    current_user_role = session.get('user_role')
    if current_user_role != 'management':
        return render_template("error.html", 
                             error="Only management can unlock accounts")
    
    user = User.query.get(user_id)
    if user:
        user.is_locked = False
        user.failed_login_attempts = 0
        db.session.commit()
    return redirect(url_for("web.users_list"))


@web_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("web.login"))