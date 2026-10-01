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

    INCIDENT_FAILURE_THRESHOLD = 3
    INCIDENT_WINDOW_MINUTES = 10

    # Database reset flag (development only)
    RESET_DB = False  # Set to False once database is stable


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
