from flask import Blueprint, request, jsonify
from extensions import db
from models import Notice
from utils.auth import roles_required, login_required, current_user
from utils.validators import require_fields

bp = Blueprint("notices", __name__, url_prefix="/api/notices")


@bp.get("")
@login_required
def list_notices():
    user = current_user()
    category = request.args.get("category")
    q = Notice.query

    if user.role == "student":
        student = user.student_profile
        q = q.filter(
            db.and_(
                db.or_(Notice.department_id.is_(None), Notice.department_id == student.department_id),
                db.or_(Notice.year_label.is_(None), Notice.year_label == student.year_label),
                db.or_(Notice.semester.is_(None), Notice.semester == student.semester),
                db.or_(Notice.division.is_(None), Notice.division.ilike("All"), Notice.division.ilike(student.division or "A")),
            )
        )
    elif user.role == "faculty":
        faculty = user.faculty_profile
        q = q.filter(
            db.or_(
                Notice.posted_by_id == user.id,
                Notice.department_id.is_(None),
                Notice.department_id == faculty.department_id,
            )
        )

    if category and category != "all":
        q = q.filter_by(category=category)
    notices = q.order_by(Notice.created_at.desc()).all()
    return jsonify({"success": True, "data": [n.to_dict() for n in notices]})


@bp.post("")
@roles_required("faculty", "admin")
def create_notice():
    from models import Department
    user = current_user()
    data = request.get_json(silent=True) or {}
    body_text = data.get("body") or data.get("content")
    if not data.get("title") or not body_text:
        require_fields(data, ["title", "body"])

    dept_id = None
    if data.get("department") and data["department"] != "All Departments":
        d = Department.resolve(data["department"])
        if d:
            dept_id = d.id

    year_val = data.get("year") if data.get("year") != "All Years" else None
    sem_val = None
    if data.get("semester") and str(data["semester"]).lower() != "all":
        try:
            sem_val = int(data["semester"])
        except (ValueError, TypeError):
            sem_val = None

    div_val = data.get("division") or "All"

    notice = Notice(
        title=data["title"].strip(),
        category=data.get("category", "General"),
        body=body_text.strip(),
        department_id=dept_id,
        year_label=year_val,
        semester=sem_val,
        division=div_val,
        posted_by_id=user.id,
    )
    db.session.add(notice)
    db.session.commit()
    return jsonify({"success": True, "data": notice.to_dict()}), 201


@bp.put("/<int:notice_id>")
@roles_required("faculty", "admin")
def update_notice(notice_id):
    from models import Department
    notice = Notice.query.get(notice_id)
    if not notice:
        return jsonify({"success": False, "error": "Notice not found."}), 404

    data = request.get_json(silent=True) or {}
    if "title" in data and data["title"].strip():
        notice.title = data["title"].strip()
    if "body" in data and data["body"].strip():
        notice.body = data["body"].strip()
    if "category" in data and data["category"].strip():
        notice.category = data["category"].strip()
    if "department" in data:
        if data["department"] and data["department"] != "All Departments":
            d = Department.resolve(data["department"])
            notice.department_id = d.id if d else None
        else:
            notice.department_id = None
    if "year" in data:
        notice.year_label = data["year"] if data["year"] != "All Years" else None
    if "semester" in data:
        try:
            notice.semester = int(data["semester"])
        except (ValueError, TypeError):
            notice.semester = None
    if "division" in data:
        notice.division = data["division"] or "All"

    db.session.commit()
    return jsonify({"success": True, "data": notice.to_dict()})


@bp.delete("/<int:notice_id>")
@roles_required("faculty", "admin")
def delete_notice(notice_id):
    notice = Notice.query.get(notice_id)
    if not notice:
        return jsonify({"success": False, "error": "Notice not found."}), 404
    db.session.delete(notice)
    db.session.commit()
    return jsonify({"success": True})
