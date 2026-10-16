import secrets
from flask import Blueprint, request, jsonify, session, current_app
from models import User, UserSession
from extensions import db
from utils.auth import current_user, login_required
from utils.validators import require_fields, ValidationError

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    
    # Accept 'email', 'username', 'loginId', or 'id' identifier in request payload
    identifier = (data.get("email") or data.get("username") or data.get("loginId") or data.get("id") or "").strip()
    if not identifier:
        return jsonify({"success": False, "error": "Missing required field: email or username"}), 400
    password = str(data.get("password") or "")
    if not password:
        return jsonify({"success": False, "error": "Missing required field: password"}), 400

    selected_role = data.get("role")  # optional, from the login page's role tabs

    # 1. Primary lookup by email
    user = User.query.filter(User.email.ilike(identifier)).first()

    # 2. Allow username "admin" to resolve to the administrator account
    if not user and identifier.lower() == "admin":
        user = User.query.filter(
            db.or_(User.email.ilike("admin@campus.edu"), User.email.ilike("admin"), User.role == "admin")
        ).first()

    # 3. Lookup student or faculty by code / PRN
    if not user:
        from models import Student, Faculty
        student = Student.query.filter(
            db.or_(Student.student_code.ilike(identifier), Student.prn.ilike(identifier))
        ).first()
        if student:
            user = student.user
        else:
            fac = Faculty.query.filter(Faculty.faculty_code.ilike(identifier)).first()
            if fac:
                user = fac.user

    if not user:
        return jsonify({"success": False, "error": "Invalid email/ID or password."}), 401

    password_ok = user.check_password(password)
    if not password_ok:
        from services.firebase_service import firebase_service
        if firebase_service.verify_password_with_firebase(user.email, password):
            user.set_password(password)
            db.session.commit()
            password_ok = True

    if not password_ok:
        return jsonify({"success": False, "error": "Invalid email/ID or password."}), 401

    if not user.is_active:
        return jsonify({"success": False, "error": "This account has been deactivated."}), 403

    if selected_role and selected_role != user.role:
        return jsonify({
            "success": False,
            "error": f"This account is registered as {user.role_label}, "
                     f"not {selected_role.capitalize()}. Select the correct role tab."
        }), 403

    # Generate high-entropy cryptographic token for tab-isolated session
    session_token = secrets.token_urlsafe(32)
    user_session = UserSession(
        id=session_token,
        user_id=user.id,
        role=user.role,
        is_active=True
    )
    db.session.add(user_session)
    db.session.commit()

    # Bind standard Flask session cookie to this specific user session token
    session.clear()
    session.permanent = True
    session["user_id"] = user.id
    session["role"] = user.role
    session["session_token"] = session_token

    from services.firebase_service import firebase_service
    fb_token = firebase_service.create_custom_token(str(user.id), {"role": user.role})

    return jsonify({
        "success": True,
        "data": user.to_dict(),
        "user": user.to_dict(),
        "mustChangePassword": bool(getattr(user, "must_change_password", False)),
        "sessionToken": session_token,
        "firebaseCustomToken": fb_token,
    })


@bp.post("/firebase-login")
def firebase_login():
    """Authenticates a user via verified Firebase ID token from the client SDK."""
    data = request.get_json(silent=True) or {}
    id_token = data.get("idToken") or data.get("id_token")
    if not id_token:
        return jsonify({"success": False, "error": "Missing Firebase ID token."}), 400

    from services.firebase_service import firebase_service
    decoded = firebase_service.verify_firebase_id_token(id_token)
    if not decoded:
        return jsonify({"success": False, "error": "Invalid or expired Firebase ID token."}), 401

    email = decoded.get("email")
    uid = decoded.get("uid")
    user = None
    if uid and str(uid).isdigit():
        user = db.session.get(User, int(uid))
    if not user and email:
        user = User.query.filter(User.email.ilike(email)).first()

    if not user:
        return jsonify({"success": False, "error": "User account matching Firebase credentials not found."}), 404

    if not user.is_active:
        return jsonify({"success": False, "error": "This account has been deactivated."}), 403

    session_token = secrets.token_urlsafe(32)
    user_session = UserSession(
        id=session_token,
        user_id=user.id,
        role=user.role,
        is_active=True
    )
    db.session.add(user_session)
    db.session.commit()

    session.clear()
    session.permanent = True
    session["user_id"] = user.id
    session["role"] = user.role
    session["session_token"] = session_token

    return jsonify({
        "success": True,
        "data": user.to_dict(),
        "user": user.to_dict(),
        "mustChangePassword": bool(getattr(user, "must_change_password", False)),
        "sessionToken": session_token,
    })


@bp.post("/first-login-setup")
@login_required
def first_login_setup():
    """First-time password setup for accounts requiring password activation.
    Validates strong password requirements, confirms matching confirmation,
    rejects reusing the initial temporary phone credential, updates the authoritative hash,
    syncs to Firebase Authentication, and clears the must_change_password flag.
    """
    user = current_user()
    data = request.get_json(silent=True) or {}
    require_fields(data, ["newPassword", "confirmPassword"])

    new_password = str(data["newPassword"]).strip()
    confirm_password = str(data["confirmPassword"]).strip()

    if new_password != confirm_password:
        raise ValidationError("New password and confirmation do not match.")

    # Disallow reusing temporary mobile number as new password
    if user.phone and new_password == str(user.phone).strip():
        raise ValidationError("New password cannot be your mobile number. Choose a secure, personalized password.")

    # Disallow unchanged current password
    if user.check_password(new_password):
        raise ValidationError("New password cannot be the same as your initial temporary password.")

    if len(new_password) < 8:
        raise ValidationError("New password must be at least 8 characters long.")

    has_upper = any(c.isupper() for c in new_password)
    has_lower = any(c.islower() for c in new_password)
    has_digit_or_punct = any(not c.isalpha() for c in new_password)
    if not (has_upper and has_lower and has_digit_or_punct):
        raise ValidationError(
            "Password must contain at least one uppercase letter, one lowercase letter, and one number or special character."
        )

    user.set_password(new_password)
    user.must_change_password = False

    # Authoritative sync with Firebase Authentication
    from services.firebase_service import firebase_service
    firebase_service.sync_user_to_firebase_auth(
        uid=str(user.id),
        email=user.email,
        password=new_password,
        display_name=user.full_name,
        role=user.role,
    )

    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Password setup successfully completed. Your account is now active.",
        "user": user.to_dict(),
        "data": user.to_dict(),
        "mustChangePassword": False,
    })


@bp.post("/change-password")
@login_required
def change_password():
    user = current_user()
    data = request.get_json(silent=True) or {}
    require_fields(data, ["currentPassword", "newPassword", "confirmPassword"])
    current_password = str(data["currentPassword"])
    new_password = str(data["newPassword"]).strip()
    confirm_password = str(data["confirmPassword"]).strip()

    if not user.check_password(current_password):
        return jsonify({"success": False, "error": "Current password is incorrect."}), 400
    if len(new_password) < 8:
        raise ValidationError("New password must be at least 8 characters long.")
    has_upper = any(c.isupper() for c in new_password)
    has_lower = any(c.islower() for c in new_password)
    has_digit_or_punct = any(not c.isalpha() for c in new_password)
    if not (has_upper and has_lower and has_digit_or_punct):
        raise ValidationError("Password must contain at least one uppercase letter, one lowercase letter, and one number or special character.")
    if new_password != confirm_password:
        raise ValidationError("New password and confirmation do not match.")
    if new_password == current_password:
        raise ValidationError("New password must be different from the current password.")

    user.set_password(new_password)
    user.must_change_password = False
    from services.firebase_service import firebase_service
    firebase_service.sync_user_to_firebase_auth(
        uid=str(user.id),
        email=user.email,
        password=new_password,
        display_name=user.full_name,
        role=user.role,
    )
    db.session.commit()
    return jsonify({
        "success": True,
        "message": "Password updated successfully.",
        "user": user.to_dict(),
        "mustChangePassword": False,
    })


@bp.post("/logout")
def logout():
    token = request.headers.get("X-Session-Token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
    if not token:
        token = session.get("session_token")

    if token:
        user_session = UserSession.query.filter_by(id=token).first()
        if user_session:
            user_session.is_active = False
            db.session.commit()
    else:
        user_id = session.get("user_id")
        if user_id:
            UserSession.query.filter_by(user_id=user_id, is_active=True).update({"is_active": False})
            db.session.commit()

    session.clear()
    resp = jsonify({"success": True})
    cookie_name = current_app.config.get("SESSION_COOKIE_NAME", "campus_session")
    resp.delete_cookie(cookie_name, path="/")
    resp.delete_cookie("session", path="/")
    resp.delete_cookie("campus_fb_session", path="/")
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return resp


@bp.get("/me")
@login_required
def me():
    user = current_user()
    token = request.headers.get("X-Session-Token") or session.get("session_token")
    return jsonify({
        "success": True,
        "data": user.to_dict(),
        "sessionToken": token,
    })
