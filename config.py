import os
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=BASE_DIR / ".env")


def _normalize_db_url(url: str) -> str:
    """Render (and some cloud providers) hand out postgres:// or postgresql:// URLs;
    SQLAlchemy with modern Psycopg 3 requires postgresql+psycopg://."""
    if not url:
        return url
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

    # Backend selection: 'firebase' (default) or 'postgres'
    DATABASE_BACKEND = os.environ.get("DATABASE_BACKEND", "firebase").lower()
    FIREBASE_DATABASE_URL = os.environ.get(
        "FIREBASE_DATABASE_URL", "https://campus-mini2-default-rtdb.firebaseio.com/"
    )
    FIREBASE_SERVICE_ACCOUNT_KEY = os.environ.get("FIREBASE_SERVICE_ACCOUNT_KEY")
    FIREBASE_CREDENTIALS_PATH = os.environ.get("FIREBASE_CREDENTIALS_PATH")

    if DATABASE_BACKEND == "firebase":
        instance_dir = BASE_DIR / "instance"
        instance_dir.mkdir(exist_ok=True)
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{str((instance_dir / 'campus_connect_rtdb.sqlite').resolve())}"
        SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_pre_ping": True,
        }
    else:
        _raw_db_url = os.environ.get("DATABASE_URL") or "postgresql+psycopg://postgres:postgres@localhost:5432/campus_connect"
        SQLALCHEMY_DATABASE_URI = _normalize_db_url(_raw_db_url)
        SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_size": 10,
            "max_overflow": 20,
            "pool_timeout": 30,
            "pool_recycle": 300,
            "pool_pre_ping": True,
        }

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Session-based auth settings
    SESSION_COOKIE_NAME = "campus_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

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

    # Brevo Transactional Email Settings
    BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
    BREVO_SENDER_EMAIL = os.environ.get("BREVO_SENDER_EMAIL", "no-reply@campus.edu")
    BREVO_SENDER_NAME = os.environ.get("BREVO_SENDER_NAME", "Campus Connect ERP")
    ERP_LOGIN_URL = os.environ.get("ERP_LOGIN_URL", "http://localhost:5000/login.html")


class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    DEBUG = False
    # Use SECURE cookies in production, but allow override if testing locally over HTTP
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "true").lower() in ("true", "1")


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}
