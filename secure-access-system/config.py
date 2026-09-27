# config.py
# Central configuration file

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-secret-key-change-in-env-file")

    SQLALCHEMY_DATABASE_URI = "sqlite:///secure_access.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT Configuration
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-only-jwt-key-change-in-env-file")
    JWT_ACCESS_TOKEN_EXPIRES = 60 * 60  # 1 hour

    # Demo Management Account (DEV ONLY)
    DEMO_USER_EMAIL = "demo@building.local"
    DEMO_USER_PASSWORD = os.environ.get("DEMO_USER_PASSWORD", "DemoPass123")

    # Database reset flag (development only)
    RESET_DB = False  # Set to False once database is stable


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
