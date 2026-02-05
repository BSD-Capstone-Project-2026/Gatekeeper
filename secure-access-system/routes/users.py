# routes/users.py
# Management / Concierge user creation

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from models import db, User
import secrets
import string

users_bp = Blueprint("users", __name__, url_prefix="/api/users")

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

@users_bp.route("/create", methods=["POST"])
@jwt_required()
def create_user():
    user_id = get_jwt_identity()
    claims = get_jwt()
    creator_role = claims["role"]

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    first_name = data.get("first_name")
    last_name = data.get("last_name")
    email = data.get("email")
    role = data.get("role")

    if not all([first_name, last_name, email, role]):
        return jsonify({"error": "Missing required fields"}), 400

    # Role enforcement
    if creator_role == "management":
        allowed_roles = ["concierge", "resident"]
    elif creator_role == "concierge":
        allowed_roles = ["resident"]
    else:
        return jsonify({"error": "Unauthorized"}), 403

    if role not in allowed_roles:
        return jsonify({"error": "Role not permitted"}), 403

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "User already exists"}), 409

    # Generate system credentials
    temp_password = generate_password()
    username = generate_username(first_name, last_name)

    user = User(
        first_name=first_name,
        last_name=last_name,
        username=username,
        email=email,
        role=role
    )
    user.set_password(temp_password)  # This also stores temp_password in DB

    db.session.add(user)
    db.session.commit()

    return jsonify({
        "message": "User created successfully",
        "created_user": {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "role": user.role,
            "temporary_password": temp_password  # Show it once
        }
    }), 201

@users_bp.route("/list", methods=["GET"])
@jwt_required()
def list_users():
    """List all users (management can see all, concierge only see residents)"""
    claims = get_jwt()
    role = claims["role"]
    
    if role == "management":
        users = User.query.all()
    elif role == "concierge":
        users = User.query.filter_by(role="resident").all()
    else:
        return jsonify({"error": "Unauthorized"}), 403
    
    user_list = []
    for user in users:
        user_list.append({
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active,
            "is_locked": user.is_locked,
            "failed_login_attempts": user.failed_login_attempts,
            "created_at": user.created_at.isoformat() if user.created_at else None
        })
    
    return jsonify({"users": user_list}), 200

@users_bp.route("/unlock", methods=["POST"])
@jwt_required()
def unlock_user():
    """Unlock a locked user account (management only)"""
    claims = get_jwt()
    if claims["role"] != "management":
        return jsonify({"error": "Only management can unlock accounts"}), 403
    
    data = request.get_json()
    email = data.get("email")
    
    if not email:
        return jsonify({"error": "Email required"}), 400
    
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    user.is_locked = False
    user.failed_login_attempts = 0
    db.session.commit()
    
    return jsonify({
        "message": "Account unlocked successfully",
        "user": {
            "email": user.email,
            "username": user.username,
            "is_locked": user.is_locked,
            "failed_attempts": user.failed_login_attempts
        }
    }), 200