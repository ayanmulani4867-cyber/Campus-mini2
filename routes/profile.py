from flask import Blueprint, request, jsonify
from extensions import db
from models import Department
from utils.auth import login_required, current_user
from utils.validators import validate_email, validate_phone, ValidationError

bp = Blueprint("profile", __name__, url_prefix="/api/profile")


@bp.get("")
@login_required
def get_profile():
    user = current_user()
    return jsonify({"success": True, "data": user.to_dict()})


@bp.put("")
@login_required
def update_profile():
    user = current_user()
    data = request.get_json(silent=True) or {}

    if "name" in data and data["name"].strip():
        user.full_name = data["name"].strip()

    if "email" in data and data["email"].strip():
        new_email = validate_email(data["email"])
        if new_email != user.email:
            from models import User
            if User.query.filter_by(email=new_email).first():
                raise ValidationError("That email is already in use.")
            user.email = new_email

    if "phone" in data:
        phone = validate_phone(str(data["phone"]).strip())
        if not phone:
            raise ValidationError("Phone number cannot be empty.")
        user.phone = phone

    if "dept" in data and data["dept"].strip():
        dept = Department.query.filter_by(name=data["dept"].strip()).first()
        if not dept:
            raise ValidationError(f"Unknown department: {data['dept']}")
        if user.student_profile:
            user.student_profile.department_id = dept.id
        elif user.faculty_profile:
            user.faculty_profile.department_id = dept.id

    db.session.commit()
    return jsonify({"success": True, "data": user.to_dict()})
