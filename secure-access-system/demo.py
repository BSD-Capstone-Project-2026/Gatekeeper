# unlock_demo.py
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db, User

app = create_app()
with app.app_context():
    user = User.query.filter_by(email='demo@building.local').first()
    if user:
        user.is_locked = False
        user.failed_login_attempts = 0
        db.session.commit()
        print("✅ Demo account unlocked!")
        print(f"   Email: {user.email}")
        print(f"   Failed attempts: {user.failed_login_attempts}")
        print(f"   Is locked: {user.is_locked}")
    else:
        print("❌ Demo account not found!")