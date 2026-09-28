import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db, User

with create_app().app_context():
    count = User.query.filter(User.temporary_password.isnot(None)).update({User.temporary_password: None})
    db.session.commit()
    print(f"Cleared {count} stored plain-text passwords.")
