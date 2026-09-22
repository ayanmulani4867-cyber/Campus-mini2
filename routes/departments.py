from flask import Blueprint, request, jsonify
from extensions import db
from models import Department
from utils.auth import roles_required, login_required
from utils.validators import require_fields, ValidationError

bp = Blueprint("departments", __name__, url_prefix="/api/departments")


@bp.get("")
@login_required
def list_departments():
    depts = Department.query.order_by(Department.name).all()
    return jsonify({"success": True, "data": [d.to_dict() for d in depts]})


@bp.post("")
@roles_required("admin")
def create_department():
    data = request.get_json(silent=True) or {}
    require_fields(data, ["name", "code"])
    if Department.query.filter_by(name=data["name"]).first():
        raise ValidationError("A department with that name already exists.")
    dept = Department(name=data["name"].strip(), code=data["code"].strip().upper())
    db.session.add(dept)
    db.session.commit()
    return jsonify({"success": True, "data": dept.to_dict()}), 201


@bp.put("/<int:dept_id>")
@roles_required("admin")
def update_department(dept_id):
    dept = Department.query.get(dept_id)
    if not dept:
        return jsonify({"success": False, "error": "Department not found."}), 404
    data = request.get_json(silent=True) or {}
    if "name" in data and data["name"].strip():
        dept.name = data["name"].strip()
    if "code" in data and data["code"].strip():
        dept.code = data["code"].strip().upper()
    db.session.commit()
    return jsonify({"success": True, "data": dept.to_dict()})


@bp.delete("/<int:dept_id>")
@roles_required("admin")
def delete_department(dept_id):
    dept = Department.query.get(dept_id)
    if not dept:
        return jsonify({"success": False, "error": "Department not found."}), 404
    if dept.students or dept.faculty or dept.courses:
        raise ValidationError("Cannot delete a department that still has students, faculty, or courses.")
    db.session.delete(dept)
    db.session.commit()
    return jsonify({"success": True})
