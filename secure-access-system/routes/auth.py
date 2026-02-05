# routes/auth.py
# Authentication (LOGIN ONLY)

from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from models import db, User
from config import Config

# Define blueprint FIRST
auth_bp = Blueprint("auth", __name__, url_prefix="/api")

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()

    if not data:
        return jsonify({"error": "No data provided"}), 400

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400

    user = User.query.filter_by(email=email).first()

    # PHASE 1 RESTRICTION: Only demo management can log in
    if email != Config.DEMO_USER_EMAIL:
        return jsonify({"error": "Invalid credentials"}), 401
    
    if not user or not user.is_active:
        return jsonify({"error": "Invalid credentials"}), 401

    # Check if account is locked
    if user.is_locked:
        return jsonify({"error": "Account is locked. Contact management."}), 401

    if not user.check_password(password):
        # For demo account, don't lock it - just return error
        if email != Config.DEMO_USER_EMAIL:
            # For non-demo accounts, track failed attempts
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= 3:
                user.is_locked = True
        db.session.commit()
        return jsonify({"error": "Invalid credentials"}), 401

    # Reset failed attempts on successful login
    user.failed_login_attempts = 0
    db.session.commit()

    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={"role": user.role}
    )

    return jsonify({
        "message": "Login successful",
        "access_token": access_token,
        "user": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "role": user.role,
            "first_name": user.first_name,
            "last_name": user.last_name
        }
    }), 200