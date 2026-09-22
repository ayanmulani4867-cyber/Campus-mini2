import secrets
from flask import Blueprint, request, jsonify, session
from models import User, UserSession
from extensions import db
from utils.auth import current_user, login_required
from utils.validators import require_fields, ValidationError

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    
    # Accept either 'email' or 'username' identifier in request payload
    identifier = (data.get("email") or data.get("username") or "").strip()
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

    if not user or not user.check_password(password):
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

    # Maintain standard Flask session cookie as secondary fallback
    session.clear()
    session.permanent = True
    session["user_id"] = user.id
    session["role"] = user.role

    return jsonify({
        "success": True,
        "data": user.to_dict(),
        "sessionToken": session_token
    })


@bp.post("/change-password")
@login_required
def change_password():
    user = current_user()
    data = request.get_json(silent=True) or {}
    require_fields(data, ["currentPassword", "newPassword", "confirmPassword"])
    current_password = str(data["currentPassword"])
    new_password = str(data["newPassword"])
    confirm_password = str(data["confirmPassword"])

    if not user.check_password(current_password):
        return jsonify({"success": False, "error": "Current password is incorrect."}), 400
    if len(new_password) < 6:
        raise ValidationError("New password must be at least 6 characters long.")
    if new_password != confirm_password:
        raise ValidationError("New password and confirmation do not match.")
    if new_password == current_password:
        raise ValidationError("New password must be different from the current password.")

    user.set_password(new_password)
    db.session.commit()
    return jsonify({"success": True, "message": "Password updated successfully."})


@bp.post("/logout")
def logout():
    token = request.headers.get("X-Session-Token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()

    if token:
        user_session = UserSession.query.filter_by(id=token).first()
        if user_session:
            user_session.is_active = False
            db.session.commit()

    session.clear()
    return jsonify({"success": True})


@bp.get("/me")
@login_required
def me():
    user = current_user()
    return jsonify({"success": True, "data": user.to_dict()})
