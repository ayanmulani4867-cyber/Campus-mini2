from datetime import date
from flask import Blueprint, request, jsonify
from extensions import db
from models import LeaveRequest, Student, User
from utils.auth import login_required, roles_required, current_user
from utils.validators import require_fields, ValidationError

bp = Blueprint("leaves", __name__, url_prefix="/api/leaves")


@bp.get("")
@login_required
def list_leaves():
    user = current_user()
    query = LeaveRequest.query

    if user.role == "student":
        student = user.student_profile
        if not student:
            return jsonify({"success": True, "data": []})
        query = query.filter_by(student_id=student.id)
    elif user.role == "faculty":
        fac = user.faculty_profile
        if fac and fac.department_id:
            # Faculty sees leaves from their department or classes
            query = query.join(Student).filter(Student.department_id == fac.department_id)
    # Admin sees all leaves

    status_filter = request.args.get("status")
    if status_filter:
        query = query.filter(LeaveRequest.status == status_filter.lower())

    leaves = query.order_by(LeaveRequest.created_at.desc()).all()
    return jsonify({"success": True, "data": [lv.to_dict() for lv in leaves]})


@bp.post("")
@roles_required("student")
def apply_leave():
    user = current_user()
    student = user.student_profile
    if not student:
        return jsonify({"success": False, "error": "Student profile not found."}), 404

    data = request.get_json(silent=True) or {}
    raw_start = data.get("startDate") or data.get("start_date")
    raw_end = data.get("endDate") or data.get("end_date")
    if not raw_start or not raw_end or not data.get("reason"):
        require_fields(data, ["startDate", "endDate", "reason"])

    try:
        start_d = date.fromisoformat(str(raw_start)[:10])
        end_d = date.fromisoformat(str(raw_end)[:10])
    except (ValueError, TypeError):
        raise ValidationError("Invalid date format. Use YYYY-MM-DD.")

    if start_d > end_d:
        raise ValidationError("Start date cannot be after end date.")

    leave_req = LeaveRequest(
        student_id=student.id,
        leave_type=data.get("leaveType") or data.get("leave_type") or "Personal",
        start_date=start_d,
        end_date=end_d,
        reason=str(data["reason"]).strip(),
        status="pending",
    )
    db.session.add(leave_req)
    db.session.commit()

    return jsonify({"success": True, "data": leave_req.to_dict()}), 201


@bp.get("/my")
@roles_required("student")
def my_leaves():
    user = current_user()
    student = user.student_profile
    if not student:
        return jsonify({"success": True, "data": []})
    leaves = LeaveRequest.query.filter_by(student_id=student.id).order_by(LeaveRequest.created_at.desc()).all()
    return jsonify({"success": True, "data": [lv.to_dict() for lv in leaves]})


@bp.get("/<int:leave_id>")
@login_required
def get_leave(leave_id):
    user = current_user()
    leave_req = LeaveRequest.query.get(leave_id)
    if not leave_req:
        return jsonify({"success": False, "error": "Leave request not found."}), 404

    if user.role == "student" and leave_req.student.user_id != user.id:
        return jsonify({"success": False, "error": "Forbidden."}), 403

    return jsonify({"success": True, "data": leave_req.to_dict()})


@bp.put("/<int:leave_id>/status")
@roles_required("admin", "faculty")
def update_leave_status(leave_id):
    user = current_user()
    leave_req = LeaveRequest.query.get(leave_id)
    if not leave_req:
        return jsonify({"success": False, "error": "Leave request not found."}), 404

    data = request.get_json(silent=True) or {}
    require_fields(data, ["status"])

    new_status = str(data["status"]).lower()
    if new_status not in ("approved", "rejected", "pending"):
        raise ValidationError("Status must be 'approved', 'rejected', or 'pending'.")

    leave_req.status = new_status
    leave_req.reviewed_by_id = user.id
    remark = data.get("remarks") or data.get("review_remarks")
    if remark is not None:
        leave_req.review_remarks = str(remark).strip()

    db.session.commit()
    return jsonify({"success": True, "data": leave_req.to_dict()})


@bp.delete("/<int:leave_id>")
@login_required
def cancel_leave(leave_id):
    user = current_user()
    leave_req = LeaveRequest.query.get(leave_id)
    if not leave_req:
        return jsonify({"success": False, "error": "Leave request not found."}), 404

    if user.role == "student":
        if leave_req.student.user_id != user.id:
            return jsonify({"success": False, "error": "Forbidden."}), 403
        if leave_req.status != "pending":
            return jsonify({"success": False, "error": "Only pending leave requests can be cancelled."}), 400

    db.session.delete(leave_req)
    db.session.commit()
    return jsonify({"success": True, "message": "Leave request deleted."})
