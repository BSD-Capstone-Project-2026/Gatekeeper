from cryptography.fernet import Fernet
from flask import current_app


def _fernet():
    return Fernet(current_app.config["ENCRYPTION_KEY"])


def encrypt(value):
    return _fernet().encrypt(value.encode()).decode()


def decrypt(token):
    return _fernet().decrypt(token.encode()).decode()
