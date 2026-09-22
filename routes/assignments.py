from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from extensions import db
from models import Assignment, AssignmentSubmission, Course, Student, Faculty, Enrollment
from utils.auth import login_required, roles_required, current_user
from utils.validators import require_fields, ValidationError

bp = Blueprint("assignments", __name__, url_prefix="/api/assignments")


@bp.get("")
@login_required
def list_assignments():
    user = current_user()
    query = Assignment.query

    course_code = request.args.get("courseCode")
    if course_code:
        course = Course.query.filter_by(code=course_code).first()
        if course:
            query = query.filter_by(course_id=course.id)

    if user.role == "student":
        student = user.student_profile
        if not student:
            return jsonify({"success": True, "data": []})

        # Get enrolled courses
        enrolled_ids = [e.course_id for e in student.enrollments]
        query = query.filter(
            Assignment.course_id.in_(enrolled_ids),
            db.or_(Assignment.division == "All", Assignment.division == student.division),
        )
        assignments = query.order_by(Assignment.due_date.asc()).all()
        return jsonify({"success": True, "data": [a.to_dict(student_id=student.id) for a in assignments]})

    elif user.role == "faculty":
        fac = user.faculty_profile
        if fac:
            assigned_cids = [a.course_id for a in fac.assignments]
            if assigned_cids:
                query = query.filter(Assignment.course_id.in_(assigned_cids))
        assignments = query.order_by(Assignment.created_at.desc()).all()
        return jsonify({"success": True, "data": [a.to_dict() for a in assignments]})

    # Admin: all assignments
    assignments = query.order_by(Assignment.created_at.desc()).all()
    return jsonify({"success": True, "data": [a.to_dict() for a in assignments]})


@bp.post("")
@roles_required("faculty", "admin")
def create_assignment():
    user = current_user()
    data = request.get_json(silent=True) or {}
    require_fields(data, ["title", "courseCode", "dueDate"])

    course = Course.query.filter_by(code=data["courseCode"]).first()
    if not course:
        return jsonify({"success": False, "error": "Course not found."}), 404

    fac_id = None
    if user.role == "faculty":
        fac_id = user.faculty_profile.id
    elif user.role == "admin":
        if "facultyId" in data:
            fac = Faculty.query.filter_by(faculty_code=data["facultyId"]).first()
            if fac:
                fac_id = fac.id
        if not fac_id and course.instructor_id:
            fac_id = course.instructor_id
        if not fac_id:
            first_fac = Faculty.query.first()
            fac_id = first_fac.id if first_fac else None

    if not fac_id:
        return jsonify({"success": False, "error": "Faculty instructor is required."}), 400

    try:
        due_d = datetime.fromisoformat(str(data["dueDate"]).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        raise ValidationError("Invalid due date format. Use ISO format (YYYY-MM-DDTHH:MM).")

    assignment = Assignment(
        title=str(data["title"]).strip(),
        description=data.get("description"),
        course_id=course.id,
        faculty_id=fac_id,
        year_label=data.get("year", f"{course.semester//2 + 1}th Year" if course.semester else "1st Year"),
        semester=course.semester,
        division=(data.get("division") or "All").strip().upper(),
        due_date=due_d,
        total_points=int(data.get("totalPoints", 100)),
    )
    db.session.add(assignment)
    db.session.commit()

    return jsonify({"success": True, "data": assignment.to_dict()}), 201


@bp.get("/<int:assignment_id>")
@login_required
def get_assignment(assignment_id):
    user = current_user()
    assignment = Assignment.query.get(assignment_id)
    if not assignment:
        return jsonify({"success": False, "error": "Assignment not found."}), 404

    if user.role == "student":
        student = user.student_profile
        return jsonify({"success": True, "data": assignment.to_dict(student_id=student.id if student else None)})

    data = assignment.to_dict()
    data["submissions"] = [s.to_dict() for s in assignment.submissions]
    return jsonify({"success": True, "data": data})


@bp.post("/<int:assignment_id>/submit")
@roles_required("student")
def submit_assignment(assignment_id):
    from services.storage_service import storage_service
    user = current_user()
    student = user.student_profile
    if not student:
        return jsonify({"success": False, "error": "Student profile not found."}), 404

    assignment = Assignment.query.get(assignment_id)
    if not assignment:
        return jsonify({"success": False, "error": "Assignment not found."}), 404

    text_content = ""
    file_bytes = None
    file_name = None
    file_size = 0
    mime_type = None

    if request.is_json:
        data = request.get_json(silent=True) or {}
        text_content = data.get("submissionText", "").strip()
    else:
        text_content = (request.form.get("submissionText") or "").strip()
        uploaded = request.files.get("file")
        if uploaded and uploaded.filename:
            try:
                validated = storage_service.validate_and_read(uploaded)
                file_bytes = validated["file_bytes"]
                file_name = validated["file_name"]
                file_size = validated["file_size_bytes"]
                mime_type = validated["mime_type"]
            except ValueError as e:
                raise ValidationError(str(e))

    if not text_content and not file_bytes:
        raise ValidationError("Please provide a submission text or upload a file (PDF, PPT, or PPTX).")

    existing = AssignmentSubmission.query.filter_by(assignment_id=assignment.id, student_id=student.id).first()
    if existing:
        if text_content:
            existing.submission_text = text_content
        if file_bytes:
            existing.file_data = file_bytes
            existing.file_name = file_name
            existing.file_size_bytes = file_size
            existing.mime_type = mime_type
            existing.file_path = None
        existing.submitted_at = datetime.now(timezone.utc)
        existing.status = "submitted"
        db.session.commit()
        return jsonify({"success": True, "data": existing.to_dict()})

    submission = AssignmentSubmission(
        assignment_id=assignment.id,
        student_id=student.id,
        submission_text=text_content or None,
        file_data=file_bytes,
        file_name=file_name,
        file_size_bytes=file_size,
        mime_type=mime_type,
        file_path=None,
        submitted_at=datetime.now(timezone.utc),
        status="submitted",
    )
    db.session.add(submission)
    db.session.commit()

    return jsonify({"success": True, "data": submission.to_dict()}), 201


@bp.get("/<int:assignment_id>/submissions/<int:submission_id>/download")
@login_required
def download_submission(assignment_id, submission_id):
    from services.storage_service import storage_service
    user = current_user()
    submission = AssignmentSubmission.query.filter_by(id=submission_id, assignment_id=assignment_id).first()
    if not submission:
        return jsonify({"success": False, "error": "Submission not found."}), 404

    # Authorization
    if user.role == "student":
        student = user.student_profile
        if not student or submission.student_id != student.id:
            return jsonify({"success": False, "error": "You cannot access another student's submission."}), 403
    elif user.role == "faculty":
        faculty = user.faculty_profile
        assignment = submission.assignment
        is_owner = (assignment.faculty_id == faculty.id) or (assignment.course.instructor_id == faculty.id) or any(
            a.course_id == assignment.course_id for a in faculty.assignments
        )
        if not is_owner:
            return jsonify({"success": False, "error": "You do not have permission to view this submission."}), 403

    if submission.file_data:
        return storage_service.create_download_response(
            submission.file_data,
            submission.file_name or f"submission_{submission.id}.pdf",
            submission.mime_type,
        )

    return jsonify({"success": False, "error": "No file attached to this submission."}), 404


@bp.post("/<int:assignment_id>/grade")
@roles_required("faculty", "admin")
def grade_submission(assignment_id):
    user = current_user()
    data = request.get_json(silent=True) or {}
    require_fields(data, ["studentId", "grade"])

    student = Student.query.filter(
        db.or_(Student.student_code == data["studentId"], Student.prn == data["studentId"])
    ).first()
    if not student:
        return jsonify({"success": False, "error": "Student not found."}), 404

    submission = AssignmentSubmission.query.filter_by(
        assignment_id=assignment_id, student_id=student.id
    ).first()
    if not submission:
        return jsonify({"success": False, "error": "Submission not found for this student."}), 404

    try:
        grade_val = float(data["grade"])
    except (ValueError, TypeError):
        raise ValidationError("Grade must be a number.")

    submission.grade = grade_val
    submission.feedback = data.get("feedback")
    submission.status = "graded"
    if user.faculty_profile:
        submission.graded_by_id = user.faculty_profile.id

    db.session.commit()
    return jsonify({"success": True, "data": submission.to_dict()})


@bp.delete("/<int:assignment_id>")
@roles_required("faculty", "admin")
def delete_assignment(assignment_id):
    assignment = Assignment.query.get(assignment_id)
    if not assignment:
        return jsonify({"success": False, "error": "Assignment not found."}), 404

    db.session.delete(assignment)
    db.session.commit()
    return jsonify({"success": True, "message": "Assignment deleted."})
