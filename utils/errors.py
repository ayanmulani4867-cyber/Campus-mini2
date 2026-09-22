from flask import jsonify
from werkzeug.exceptions import HTTPException
from sqlalchemy.exc import IntegrityError, OperationalError
from utils.validators import ValidationError


def register_error_handlers(app):
    @app.errorhandler(ValidationError)
    def handle_validation_error(err):
        return jsonify({"success": False, "error": err.message}), 400

    @app.errorhandler(IntegrityError)
    def handle_integrity_error(err):
        app.logger.warning("IntegrityError: %s", err)
        return jsonify({
            "success": False,
            "error": "That record conflicts with an existing one (duplicate ID/email) "
                     "or references something that doesn't exist."
        }), 409

    @app.errorhandler(OperationalError)
    def handle_operational_error(err):
        app.logger.error("Database OperationalError: %s", err)
        return jsonify({
            "success": False,
            "error": "Database is unavailable. If DATABASE_URL is not configured yet, "
                     "set it in your environment and restart the server."
        }), 503

    @app.errorhandler(HTTPException)
    def handle_http_exception(err):
        return jsonify({"success": False, "error": err.description}), err.code

    @app.errorhandler(Exception)
    def handle_unexpected_error(err):
        app.logger.exception("Unhandled exception")
        return jsonify({"success": False, "error": "Internal server error."}), 500
