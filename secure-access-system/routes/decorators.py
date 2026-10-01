# routes/decorators.py
from functools import wraps
from flask import session, redirect, url_for, render_template, jsonify, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt
from models import db, AuditLog

def role_required(*allowed_roles):
    """Decorator for web routes: checks session user_role."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_role' not in session:
                return redirect(url_for('web.login'))
            if session['user_role'] not in allowed_roles:
                db.session.add(AuditLog(user_id=session.get('user_id'), action="access_denied",
                                        details=f"{request.method} {request.path}", performed_by=session.get('user_id')))
                db.session.commit()
                return render_template("error.html", error="Access denied. Insufficient privileges."), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def api_role_required(*allowed_roles):
    """Decorator for API routes (JWT): checks role from JWT claims."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            if claims.get('role') not in allowed_roles:
                return jsonify({"error": "Forbidden: insufficient role"}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator