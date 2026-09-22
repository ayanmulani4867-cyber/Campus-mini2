import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, render_template, send_from_directory, jsonify, request
from config import config_by_name
from extensions import db, migrate
from utils.errors import register_error_handlers
from routes import register_blueprints

BASE_DIR = Path(__file__).resolve().parent

# Load .env file for local development if present
load_dotenv(dotenv_path=BASE_DIR / ".env")


def create_app(config_name=None):
    config_name = config_name or os.environ.get("FLASK_ENV", "production")
    config_class = config_by_name.get(config_name, config_by_name["production"])

    templates_dir = getattr(config_class, "TEMPLATES_DIR", str(BASE_DIR / "templates"))
    static_dir = getattr(config_class, "STATIC_DIR", str(BASE_DIR / "static"))

    app = Flask(
        __name__,
        template_folder=templates_dir,
        static_folder=static_dir,
        static_url_path="/static",
    )
    app.config.from_object(config_class)

    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        app.logger.warning(
            "DATABASE_URL is not set. The app will start, but database operations will fail."
        )

    logging.basicConfig(level=logging.INFO if not app.debug else logging.DEBUG)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # Import models so SQLAlchemy / Alembic registers them
    import models  # noqa: F401

    # Register error handlers and API blueprints
    register_error_handlers(app)
    register_blueprints(app)

    # CORS configuration
    from flask_cors import CORS
    cors_origins = app.config.get("CORS_ORIGINS")
    if cors_origins:
        CORS(app, supports_credentials=True, origins=cors_origins,
             allow_headers=["Content-Type", "X-Session-Token", "Authorization"])
    else:
        CORS(app, supports_credentials=True, origins=r".*",
             allow_headers=["Content-Type", "X-Session-Token", "Authorization"])

    # Health check endpoint
    @app.get("/api/health")
    def health():
        db_configured = bool(app.config.get("SQLALCHEMY_DATABASE_URI"))
        return {
            "success": True,
            "status": "ok",
            "environment": config_name,
            "databaseConfigured": db_configured,
        }

    # Static asset convenience routes (handles relative paths like href="css/style.css")
    @app.get("/css/<path:filename>")
    def serve_css(filename):
        return send_from_directory(os.path.join(app.static_folder, "css"), filename)

    @app.get("/js/<path:filename>")
    def serve_js(filename):
        return send_from_directory(os.path.join(app.static_folder, "js"), filename)

    @app.get("/images/<path:filename>")
    def serve_images(filename):
        return send_from_directory(os.path.join(app.static_folder, "images"), filename)

    # Frontend Page Routes
    @app.get("/")
    def index():
        return render_template("index.html")

    # Dynamic route for HTML templates and static file fallbacks
    @app.get("/<path:path>")
    def catch_all(path):
        # Do not catch /api routes - let them return proper 404
        if path.startswith("api/"):
            return jsonify({"success": False, "error": "Not found"}), 404

        # 1. Exact match in templates (e.g., "login.html")
        template_file = os.path.join(templates_dir, path)
        if os.path.isfile(template_file):
            return render_template(path)

        # 2. Extensionless match (e.g. "login" -> "login.html")
        template_with_ext = os.path.join(templates_dir, f"{path}.html")
        if os.path.isfile(template_with_ext):
            return render_template(f"{path}.html")

        # 3. Static folder direct file fallback
        static_file = os.path.join(static_dir, path)
        if os.path.isfile(static_file):
            return send_from_directory(static_dir, path)

        # 4. Fallback to index.html for client-side routing
        return render_template("index.html")

    return app


# Root module-level application object for Gunicorn: `gunicorn app:app`
app = create_app(os.environ.get("FLASK_ENV", "production"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    dev_app = create_app(os.environ.get("FLASK_ENV", "development"))
    dev_app.run(host="127.0.0.1", port=port, debug=True)
