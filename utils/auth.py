from functools import wraps
from datetime import datetime, timedelta
from flask import request, session, jsonify
from extensions import db
from models import User, UserSession

SESSION_MAX_AGE_HOURS = 8


def get_current_session():
    """Return active UserSession if authenticated via tab-scoped token, else None."""
    token = request.headers.get("X-Session-Token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()

    if not token:
        return None

    user_session = UserSession.query.filter_by(id=token, is_active=True).first()
    if not user_session:
        return None

    # Enforce session lifetime from last activity (handling both aware and naive timestamps)
    last_act = user_session.last_activity
    if last_act:
        from datetime import timezone
        now = datetime.now(timezone.utc) if last_act.tzinfo is not None else datetime.utcnow()
        if now - last_act > timedelta(hours=SESSION_MAX_AGE_HOURS):
            user_session.is_active = False
            db.session.commit()
            return None
        user_session.last_activity = now
        db.session.commit()
    return user_session


def current_user():
    """Return the authenticated User for this request.
    
    Priority:
    1. Tab-isolated session token via X-Session-Token or Authorization Bearer.
    2. Fallback to ambient Flask session cookie only if no token header was supplied.
    """
    token_supplied = bool(
        request.headers.get("X-Session-Token") or
        request.headers.get("Authorization", "").startswith("Bearer ")
    )

    if token_supplied:
        user_session = get_current_session()
        if user_session and user_session.user and user_session.user.is_active:
            return user_session.user
        # Do not fall back to ambient cookie if client explicitly sent an invalid/expired token
        return None

    # Fallback for direct cookie-based clients
    user_id = session.get("user_id")
    if not user_id:
        return None
    user = User.query.get(user_id)
    if user and user.is_active:
        return user
    return None


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user or not user.is_active:
            return jsonify({"success": False, "error": "Authentication required."}), 401
        return fn(*args, **kwargs)
    return wrapper


def roles_required(*allowed_roles):
    """Restrict a route to one or more roles, e.g. @roles_required('admin')."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user or not user.is_active:
                return jsonify({"success": False, "error": "Authentication required."}), 401
            if user.role not in allowed_roles:
                return jsonify({
                    "success": False,
                    "error": f"Forbidden: requires role {', '.join(allowed_roles)}."
                }), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator
