# routes/dashboard.py

from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from models import User, db
from datetime import datetime, timedelta

dashboard_bp = Blueprint("dashboard_api", __name__, url_prefix="/api/dashboard")

# ---------------- DASHBOARD STATS ----------------
@dashboard_bp.route("/stats")
@login_required
def dashboard_stats():
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    locked_users = User.query.filter_by(is_locked=True).count()

    return jsonify({
        "total_users": total_users,
        "active_users": active_users,
        "locked_users": locked_users
    })


# ---------------- RECENT USERS ----------------
@dashboard_bp.route("/recent-users")
@login_required
def recent_users():
    users = (
        User.query
        .order_by(User.created_at.desc())
        .limit(5)
        .all()
    )

    return jsonify([
        {
            "id": u.id,
            "name": f"{u.first_name} {u.last_name}",
            "email": u.email,
            "role": u.role,
            "created_at": u.created_at.strftime("%Y-%m-%d")
        }
        for u in users
    ])
