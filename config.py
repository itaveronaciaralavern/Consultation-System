"""
Environment-based configuration.

Design decision: we use a class-per-environment pattern so the Application
Factory (app/__init__.py) can select a config object by name at create_app()
time (e.g. create_app('production')). This keeps secrets and environment
differences out of code paths and lets tests use a dedicated TestingConfig
with an in-memory database.
"""
import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Load .env if python-dotenv is available and a .env file exists.
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, ".env"))
except ImportError:
    pass


class BaseConfig:
    """Shared settings for every environment."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-secret-change-me")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Flask-WTF CSRF protection is on by default when Flask-WTF is
    # initialized; these settings make the intent explicit.
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None  # tokens valid for the whole session

    # Session cookie hardening (mitigates session hijacking / XSS cookie theft).
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    # Rate limiting storage. In production this should point at Redis
    # (e.g. "redis://localhost:6379"); see README "Rate limiting" note.
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_ENABLED = True

    ITEMS_PER_PAGE = 10


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DEV_DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'dev.db')}"
    )
    SESSION_COOKIE_SECURE = False  # allow plain HTTP on localhost


class ProductionConfig(BaseConfig):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "PROD_DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'prod.db')}"
    )
    SESSION_COOKIE_SECURE = True  # requires HTTPS in real production


class TestingConfig(BaseConfig):
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
