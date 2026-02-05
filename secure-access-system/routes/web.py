# routes/web.py
# Web interface for management

from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from models import db, User
from datetime import datetime, timedelta
from flask_login import login_user, login_required, current_user

web_bp = Blueprint("web", __name__)

@web_bp.route("/")
def home():
    return redirect(url_for("web.login"))


@web_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    
    email = request.form.get("email")
    password = request.form.get("password")

    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        return render_template("login.html", error="Invalid credentials")
    
    if user.role != "management":
        return render_template("login.html", error="Only management can access this portal")
    
    login_user(user)  # ✅ This makes current_user available in templates
    return redirect(url_for("web.dashboard"))

@web_bp.route("/dashboard")
@login_required
def dashboard():
    # Get all users (or last 5 users)
    users = User.query.order_by(User.created_at.desc()).all()
    
    return render_template("dashboard.html", users=users)


@web_bp.route("/api/dashboard/stats")
def dashboard_stats():
    """API endpoint to get dashboard statistics (for JavaScript fetch)"""
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    locked_users = User.query.filter_by(is_locked=True).count()
    
    # Users created in last 7 days
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_users = User.query.filter(User.created_at >= week_ago).count()
    
    # Role counts
    management_count = User.query.filter_by(role='management').count()
    concierge_count = User.query.filter_by(role='concierge').count()
    resident_count = User.query.filter_by(role='resident').count()
    
    return jsonify({
        'total_users': total_users,
        'active_users': active_users,
        'locked_users': locked_users,
        'recent_users': recent_users,
        'management_count': management_count,
        'concierge_count': concierge_count,
        'resident_count': resident_count
    })

@web_bp.route("/api/dashboard/recent-users")
def recent_users_api():
    """API endpoint to get recent users (for JavaScript fetch)"""
    users = User.query.order_by(User.created_at.desc()).limit(5).all()
    
    user_list = []
    for user in users:
        # Determine status
        if user.is_locked:
            status = 'locked'
        elif not user.is_active:
            status = 'inactive'
        else:
            status = 'active'
        
        user_list.append({
            'username': user.username,
            'email': user.email,
            'role': user.role,
            'status': status,
            'created': user.created_at.strftime('%Y-%m-%d') if user.created_at else 'N/A'
        })
    
    return jsonify({'users': user_list})

@web_bp.route("/users")
def users_list():
    """Page to view all users"""
    users = User.query.all()
    return render_template("users.html", users=users)

@web_bp.route("/create-user", methods=["GET", "POST"])
def create_user():
    """Page to create new users"""
    if request.method == "GET":
        return render_template("create_user.html")
    
    # Handle form submission
    first_name = request.form.get("first_name")
    last_name = request.form.get("last_name")
    email = request.form.get("email")
    role = request.form.get("role")
    
    if not all([first_name, last_name, email, role]):
        return render_template("create_user.html", error="All fields are required")
    
    # Check if user exists
    if User.query.filter_by(email=email).first():
        return render_template("create_user.html", error="User already exists")
    
    # Import functions from users routes
    from routes.users import generate_password, generate_username
    
    temp_password = generate_password()
    username = generate_username(first_name, last_name)
    
    # Create user
    user = User(
        first_name=first_name,
        last_name=last_name,
        username=username,
        email=email,
        role=role
    )
    user.set_password(temp_password)
    
    db.session.add(user)
    db.session.commit()
    
    # Show success with credentials
    return render_template("create_user.html",
                         success=True,
                         user_data={
                             'username': username,
                             'email': email,
                             'role': role,
                             'temp_password': temp_password
                         })

@web_bp.route("/unlock-user/<int:user_id>")
def unlock_user(user_id):
    """Unlock a user account"""
    user = User.query.get(user_id)
    if user:
        user.is_locked = False
        user.failed_login_attempts = 0
        db.session.commit()
    return redirect(url_for("web.users_list"))

@web_bp.route("/toggle-user/<int:user_id>")
def toggle_user(user_id):
    """Activate/deactivate a user"""
    user = User.query.get(user_id)
    if user:
        user.is_active = not user.is_active
        db.session.commit()
    return redirect(url_for("web.users_list"))

@web_bp.route("/logout")
def logout():
    """Logout and redirect to login"""
    return redirect(url_for("web.login"))