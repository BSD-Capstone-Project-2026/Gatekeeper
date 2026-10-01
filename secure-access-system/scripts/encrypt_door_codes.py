import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cryptography.fernet import InvalidToken
from app import create_app
from models import db, User
from utils.encryption import decrypt


def encrypt_existing():
    count = 0
    for user in User.query.filter(User._door_code.isnot(None)):
        try:
            decrypt(user._door_code)
        except InvalidToken:
            user.door_code = user._door_code
            count += 1
    db.session.commit()
    return count


if __name__ == "__main__":
    with create_app().app_context():
        print(f"Encrypted {encrypt_existing()} door codes.")
