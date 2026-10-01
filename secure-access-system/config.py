# config.py
# Central configuration file

import os
from dotenv import load_dotenv

load_dotenv()


APP_ENV = os.environ.get("APP_ENV", "development")
DEV_ENCRYPTION_KEY = "FIUm535S2jS40e-Qi4BG6W3aiL_yKA5v6xWgquo9iTY="


class Config:
    ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", None if APP_ENV == "production" else DEV_ENCRYPTION_KEY)
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-secret-key-change-in-env-file")

    SQLALCHEMY_DATABASE_URI = "sqlite:///secure_access.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT Configuration
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-only-jwt-key-change-in-env-file")
    JWT_ACCESS_TOKEN_EXPIRES = 60 * 60  # 1 hour

    # Demo Management Account (DEV ONLY)
    DEMO_USER_EMAIL = "demo@building.local"
    DEMO_USER_PASSWORD = os.environ.get("DEMO_USER_PASSWORD", "DemoPass123")

    BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups")
    BACKUP_KEEP = 10
    LOG_RETENTION_DAYS = 90

    MAIL_SERVER = os.environ.get("MAIL_SERVER")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_SENDER = os.environ.get("MAIL_SENDER", "gatekeeper@building.local")

    NETWORK_CHECK_HOST = os.environ.get("NETWORK_CHECK_HOST")
    NETWORK_CHECK_PORT = int(os.environ.get("NETWORK_CHECK_PORT", 80))

    SESSION_TIMEOUT_MINUTES = int(os.environ.get("SESSION_TIMEOUT_MINUTES", 15))

    INCIDENT_FAILURE_THRESHOLD = 3
    INCIDENT_WINDOW_MINUTES = 10

    # Database reset flag (development only)
    RESET_DB = False  # Set to False once database is stable


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
