# routes/protected.py
# JWT protected test route

from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity,get_jwt
protected_bp = Blueprint("protected", __name__, url_prefix="/api")

@protected_bp.route("/protected", methods=["GET"])
@jwt_required()
def protected():
    claims = get_jwt()
    user_id = get_jwt_identity()
    return jsonify({
    "message": "Protected route accessed",
    "user": {
        "id": user_id,
        "role": claims["role"]
    }
}), 200
