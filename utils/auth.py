from functools import wraps
from datetime import datetime, timedelta, timezone
from flask import request, session, jsonify, g
from extensions import db
from models import User, UserSession

SESSION_MAX_AGE_HOURS = 24 * 7  # 7-day session lifetime


def get_current_session_by_token(token: str):
    """Return active UserSession if valid and not expired, else None."""
    if not token or not isinstance(token, str):
        return None

    user_session = UserSession.query.filter_by(id=token, is_active=True).first()
    if not user_session:
        return None

    # Enforce session lifetime from last activity (handling both aware and naive timestamps)
    last_act = user_session.last_activity
    if last_act:
        now = datetime.now(timezone.utc) if last_act.tzinfo is not None else datetime.utcnow()
        if now - last_act > timedelta(hours=SESSION_MAX_AGE_HOURS):
            user_session.is_active = False
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
            return None

        # Throttle activity update to once every 5 minutes to prevent DB lock contention across concurrent requests
        if now - last_act > timedelta(minutes=5):
            user_session.last_activity = now
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()

    return user_session


def get_current_session():
    """Return active UserSession if authenticated via tab-scoped token, else None."""
    token = request.headers.get("X-Session-Token")
    auth_header = request.headers.get("Authorization", "").strip()
    if not token and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    if not token:
        token = request.args.get("token") or request.args.get("session_token")
    return get_current_session_by_token(token)


def _resolve_current_user():
    """Resolves and returns the authenticated User for the current request.
    
    Priority:
    1. Firebase ID token via Authorization: Bearer <id_token> or X-Firebase-Token.
    2. Firebase session cookie via campus_fb_session or __session cookie.
    3. Tab-scoped session token via X-Session-Token, Authorization Bearer, or query token.
    4. Signed Flask session cookie (campus_session).
    
    SECURITY: If the client supplies an authentication token (Firebase token or
    tab session token), authentication succeeds or fails based on that token alone.
    It NEVER silently falls back to an ambient session cookie of another user.
    """
    from services.firebase_service import firebase_service

    # 1. Check for Firebase ID Token
    raw_fb_token = request.headers.get("X-Firebase-Token")
    auth_header = request.headers.get("Authorization", "").strip()
    if not raw_fb_token and auth_header.startswith("Bearer "):
        val = auth_header[7:].strip()
        # Firebase ID tokens are standard 3-part JWTs or explicit test tokens
        if val.count(".") == 2 or val.startswith("test-token-"):
            raw_fb_token = val

    if raw_fb_token:
        decoded_claims = firebase_service.verify_firebase_id_token(raw_fb_token)
        if not decoded_claims:
            return None
        uid = decoded_claims.get("uid")
        email = decoded_claims.get("email")
        user = None
        if uid and str(uid).isdigit():
            user = db.session.get(User, int(uid))
        if not user and email:
            user = User.query.filter(User.email.ilike(email)).first()
        if user and user.is_active:
            return user
        return None

    # 2. Check for Firebase Session Cookie
    fb_cookie = request.cookies.get("campus_fb_session") or request.cookies.get("__session")
    if fb_cookie:
        decoded_claims = firebase_service.verify_session_cookie(fb_cookie)
        if decoded_claims:
            uid = decoded_claims.get("uid")
            email = decoded_claims.get("email")
            user = None
            if uid and str(uid).isdigit():
                user = db.session.get(User, int(uid))
            if not user and email:
                user = User.query.filter(User.email.ilike(email)).first()
            if user and user.is_active:
                return user
        return None

    # 3. Check for Tab-scoped session token (X-Session-Token, non-JWT Bearer, or query token)
    explicit_token = request.headers.get("X-Session-Token")
    if not explicit_token and auth_header.startswith("Bearer "):
        explicit_token = auth_header[7:].strip()
    if not explicit_token:
        explicit_token = request.args.get("token") or request.args.get("session_token")

    if explicit_token:
        user_session = get_current_session_by_token(explicit_token)
        if not user_session:
            # Token was supplied but is invalid, expired, or deactivated.
            # DO NOT fall back to cookie!
            return None
        user = user_session.user
        if user and user.is_active:
            return user
        return None

    # 4. Fallback to signed Flask session cookie ONLY when no token was explicitly supplied
    cookie_user_id = session.get("user_id")
    bound_token = session.get("session_token")
    if bound_token:
        user_session = get_current_session_by_token(bound_token)
        if user_session and user_session.user and user_session.user.is_active:
            if not cookie_user_id or user_session.user_id == cookie_user_id:
                return user_session.user
        # The session token bound to this cookie has been revoked, expired, or mismatched
        session.clear()
        return None

    # Fallback for session user_id (handles test clients using session_transaction without bound_token)
    if cookie_user_id:
        user = db.session.get(User, cookie_user_id)
        if user and user.is_active:
            return user
        session.clear()

    return None


def current_user():
    """Return the authenticated User for this request, cached on flask.g for request lifetime."""
    if hasattr(g, "_authenticated_user"):
        return g._authenticated_user
    user = _resolve_current_user()
    g._authenticated_user = user
    return user


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
