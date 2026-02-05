# config.py
# Central configuration file

class Config:
    SECRET_KEY = "dev-secret-key-change-later"

    SQLALCHEMY_DATABASE_URI = "sqlite:///secure_access.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT Configuration
    JWT_SECRET_KEY = "jwt-secret-key"
    JWT_ACCESS_TOKEN_EXPIRES = 60 * 60  # 1 hour

    # Demo Management Account (DEV ONLY)
    DEMO_USER_EMAIL = "demo@building.local"
    DEMO_USER_PASSWORD = "DemoPass123"
# Central configuration file

class Config:
    SECRET_KEY = "dev-secret-key-change-later"

    SQLALCHEMY_DATABASE_URI = "sqlite:///secure_access.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT Configuration
    JWT_SECRET_KEY = "jwt-secret-key"
    JWT_ACCESS_TOKEN_EXPIRES = 60 * 60  # 1 hour

    # Demo Management Account (DEV ONLY)
    DEMO_USER_EMAIL = "demo@building.local"
    DEMO_USER_PASSWORD = "DemoPass123"

    # Database reset flag (development only)
    RESET_DB = True  # Set to False once database is stable