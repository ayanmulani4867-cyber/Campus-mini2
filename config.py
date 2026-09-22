import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _normalize_db_url(url: str) -> str:
    """Render (and some cloud providers) hand out postgres:// URLs; SQLAlchemy
    with psycopg needs postgresql://. Normalize so both work."""
    if url and url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

    _raw_db_url = os.environ.get("DATABASE_URL") or "postgresql://postgres:postgres@localhost:5432/campus_connect"
    SQLALCHEMY_DATABASE_URI = _normalize_db_url(_raw_db_url)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # Session-based auth settings
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    # Allowed frontend origins for CORS
    CORS_ORIGINS = [
        o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()
    ]

    ENV = os.environ.get("FLASK_ENV", "production")
    DEBUG = ENV == "development"

    # Static assets and templates directories at root
    STATIC_DIR = str((BASE_DIR / "static").resolve())
    TEMPLATES_DIR = str((BASE_DIR / "templates").resolve())

    # Persistent materials upload directory (uploads/materials in project root)
    MATERIAL_UPLOAD_DIR = os.environ.get(
        "MATERIAL_UPLOAD_DIR", str((BASE_DIR / "uploads" / "materials").resolve())
    )


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}
