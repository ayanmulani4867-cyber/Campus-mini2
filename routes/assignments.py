from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from extensions import db
from models import Assignment, AssignmentSubmission, Course, Student, Faculty, Enrollment
from utils.auth import login_required, roles_required, current_user
from utils.validators import require_fields, ValidationError

bp = Blueprint("assignments", __name__, url_prefix="/api/assignments")


def _batch_serialize_assignments(assignments, student_id=None):
    if not assignments:
        return []

    course_ids = list({a.course_id for a in assignments if a.course_id})
    # Query enrollment counts per (course_id, division) in a single fast aggregation
    counts_rows = (
        db.session.query(
            Enrollment.course_id,
            Student.division,
            db.func.count(Student.id)
        )
        .join(Student, Student.id == Enrollment.student_id)
        .filter(Enrollment.course_id.in_(course_ids))
        .group_by(Enrollment.course_id, Student.division)
        .all()
    ) if course_ids else []

    # Map course_id -> {division: count, "_total": count}
    enrollment_map = {}
    for cid, div, cnt in counts_rows:
        if cid not in enrollment_map:
            enrollment_map[cid] = {"_total": 0}
        enrollment_map[cid]["_total"] += cnt
        if div:
            enrollment_map[cid][div.upper()] = cnt

    results = []
    for a in assignments:
        div_key = (a.division or "").strip().upper()
        c_map = enrollment_map.get(a.course_id, {})
        if not div_key or div_key == "ALL":
            eligible_count = c_map.get("_total", 0)
        else:
            eligible_count = c_map.get(div_key, 0)

        sub_count = len(a.submissions)
        evaluated_count = sum(1 for s in a.submissions if s.grade is not None or s.status in ("graded", "evaluated"))
        awaiting_count = max(0, sub_count - evaluated_count)

        counts = {
            "eligibleCount": eligible_count,
            "submissionsCount": sub_count,
            "evaluatedCount": evaluated_count,
            "awaitingEvaluationCount": awaiting_count,
        }
        results.append(a.to_dict(student_id=student_id, counts=counts))
    return results


@bp.get("")
@login_required
def list_assignments():
    user = current_user()
    from sqlalchemy.orm import defer
    query = Assignment.query.options(
        db.joinedload(Assignment.course),
        db.joinedload(Assignment.faculty).joinedload(Faculty.user),
        db.selectinload(Assignment.submissions).defer(AssignmentSubmission.file_data).joinedload(AssignmentSubmission.student).joinedload(Student.user)
    )

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
        return jsonify({"success": True, "data": _batch_serialize_assignments(assignments, student_id=student.id)})

    elif user.role == "faculty":
        fac = user.faculty_profile
        if fac:
            assigned_cids = [a.course_id for a in fac.assignments]
            if assigned_cids:
                query = query.filter(Assignment.course_id.in_(assigned_cids))
        assignments = query.order_by(Assignment.created_at.desc()).all()
        return jsonify({"success": True, "data": _batch_serialize_assignments(assignments)})

    # Admin: all assignments
    assignments = query.order_by(Assignment.created_at.desc()).all()
    return jsonify({"success": True, "data": _batch_serialize_assignments(assignments)})


@bp.post("")
@roles_required("faculty", "admin")
def create_assignment():
    user = current_user()
    data = request.get_json(silent=True) or {}
    c_code = (data.get("courseCode") or data.get("course_code") or "").strip()
    raw_due = data.get("dueDate") or data.get("due_date")
    if not data.get("title") or not c_code or not raw_due:
        require_fields(data, ["title", "courseCode", "dueDate"])

    course = Course.query.filter_by(code=c_code).first()
    if not course:
        return jsonify({"success": False, "error": "Course not found."}), 404

    division = (data.get("division") or "All").strip().upper()

    fac_id = None
    if user.role == "faculty":
        fac = user.faculty_profile
        fac_id = fac.id
        # Server-side RBAC: Faculty must be assigned to teach this course and division
        is_assigned = any(
            a.course_id == course.id and (a.division.upper() == division or division == "ALL" or a.division.upper() == "ALL")
            for a in fac.assignments
        ) or (course.instructor_id == fac.id)
        if not is_assigned:
            return jsonify({
                "success": False,
                "error": f"You are not assigned to teach course {course.code} for Division {division}."
            }), 403
    elif user.role == "admin":
        fac_ref = data.get("facultyId") or data.get("faculty_id")
        if fac_ref:
            fac = Faculty.query.filter(
                db.or_(Faculty.faculty_code == fac_ref, Faculty.id == int(fac_ref) if str(fac_ref).isdigit() else False)
            ).first()
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
        due_d = datetime.fromisoformat(str(raw_due).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        raise ValidationError("Invalid due date format. Use ISO format (YYYY-MM-DDTHH:MM).")

    # Module 7: Default maximum marks for this assignment workflow is 10
    raw_points = data.get("totalPoints") or data.get("total_points") or data.get("total_marks") or data.get("totalMarks")
    try:
        total_points = int(raw_points) if raw_points is not None else 10
        if total_points <= 0:
            raise ValidationError("Total marks must be positive.")
    except (ValueError, TypeError):
        total_points = 10

    assignment = Assignment(
        title=str(data["title"]).strip(),
        description=data.get("description"),
        course_id=course.id,
        faculty_id=fac_id,
        year_label=data.get("year", f"{course.semester//2 + 1}th Year" if course.semester else "3rd Year"),
        semester=course.semester,
        division=division,
        due_date=due_d,
        total_points=total_points,
    )
    db.session.add(assignment)
    db.session.commit()

    return jsonify({"success": True, "data": assignment.to_dict()}), 201


@bp.get("/<int:assignment_id>")
@login_required
def get_assignment(assignment_id):
    user = current_user()
    assignment = Assignment.query.options(
        db.joinedload(Assignment.course),
        db.joinedload(Assignment.faculty).joinedload(Faculty.user),
        db.selectinload(Assignment.submissions).defer(AssignmentSubmission.file_data).joinedload(AssignmentSubmission.student).joinedload(Student.user)
    ).get(assignment_id)
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
        text_content = (data.get("submissionText") or data.get("submission_text") or "").strip()
    else:
        text_content = (request.form.get("submissionText") or request.form.get("submission_text") or "").strip()
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
        raise ValidationError("Please provide a submission text or upload a file (PDF, DOC, DOCX, PPT, PPTX, or ZIP).")

    # Verify student is enrolled in this course
    enrolled = any(e.course_id == assignment.course_id for e in student.enrollments)
    if not enrolled:
        return jsonify({"success": False, "error": "You are not enrolled in the course for this assignment."}), 403

    if assignment.division and assignment.division.upper() != "ALL":
        if student.division and student.division.upper() != assignment.division.upper():
            return jsonify({"success": False, "error": f"This assignment is restricted to Division {assignment.division}."}), 403

    # Determine whether submission is on-time or late
    now = datetime.now(timezone.utc)
    due_dt = assignment.due_date
    if due_dt and due_dt.tzinfo is None:
        due_dt = due_dt.replace(tzinfo=timezone.utc)
    is_late = bool(due_dt and now > due_dt)
    submission_status = "late" if is_late else "submitted"

    existing = AssignmentSubmission.query.filter_by(assignment_id=assignment.id, student_id=student.id).first()
    if existing and existing.is_locked:
        # Module 8 & 10: Reject modification attempts and record audit log
        from models import log_audit
        log_audit(
            action="ASSIGNMENT_LOCKED_ATTEMPT",
            target_type="AssignmentSubmission",
            target_id=existing.id,
            details=f"Student {student.student_code} attempted to edit/resubmit locked assignment {assignment.id} ({assignment.title}).",
            user=user
        )
        return jsonify({
            "success": False,
            "error": "Assignment submitted successfully. Editing and resubmission are disabled.",
            "isLocked": True,
            "data": existing.to_dict()
        }), 403

    if existing and not existing.is_locked:
        # Exceptional correction granted by authorized HOD/admin
        from models import log_audit
        if text_content:
            existing.submission_text = text_content
        if file_bytes:
            existing.file_data = file_bytes
            existing.file_name = file_name
            existing.file_size_bytes = file_size
            existing.mime_type = mime_type
            existing.file_path = None
        existing.submitted_at = now
        existing.status = submission_status
        existing.is_locked = True  # Re-lock after exceptional resubmission
        db.session.commit()
        log_audit(
            action="ASSIGNMENT_CORRECTION_SUBMIT",
            target_type="AssignmentSubmission",
            target_id=existing.id,
            reason=existing.unlock_reason,
            details=f"Exceptional correction submitted for assignment {assignment.id}.",
            user=user
        )
        return jsonify({
            "success": True,
            "message": "Assignment submitted successfully. Editing and resubmission are disabled.",
            "isLocked": True,
            "data": existing.to_dict()
        })

    # New submission: lock immediately upon successful save
    submission = AssignmentSubmission(
        assignment_id=assignment.id,
        student_id=student.id,
        submission_text=text_content or None,
        file_data=file_bytes,
        file_name=file_name,
        file_size_bytes=file_size,
        mime_type=mime_type,
        file_path=None,
        submitted_at=now,
        status=submission_status,
        is_locked=True,
    )
    db.session.add(submission)
    db.session.commit()

    from models import log_audit
    log_audit(
        action="ASSIGNMENT_SUBMIT",
        target_type="AssignmentSubmission",
        target_id=submission.id,
        details=f"Student {student.student_code} successfully submitted assignment {assignment.id} ({assignment.title}). Submission locked.",
        user=user
    )

    return jsonify({
        "success": True,
        "message": "Assignment submitted successfully. Editing and resubmission are disabled.",
        "isLocked": True,
        "data": submission.to_dict()
    }), 201


@bp.get("/<int:assignment_id>/evaluation-roster")
@roles_required("faculty", "admin")
def get_evaluation_roster(assignment_id):
    """Returns the full evaluation roster: eligible students with submission and evaluation statuses."""
    user = current_user()
    assignment = Assignment.query.options(
        db.joinedload(Assignment.course),
        db.joinedload(Assignment.faculty).joinedload(Faculty.user),
        db.selectinload(Assignment.submissions).defer(AssignmentSubmission.file_data).joinedload(AssignmentSubmission.student).joinedload(Student.user)
    ).get(assignment_id)
    if not assignment:
        return jsonify({"success": False, "error": "Assignment not found."}), 404

    if user.role == "faculty":
        fac = user.faculty_profile
        is_assigned = any(
            a.course_id == assignment.course_id and (
                a.division.upper() == assignment.division.upper() or
                assignment.division.upper() == "ALL" or
                a.division.upper() == "ALL"
            )
            for a in fac.assignments
        ) or (assignment.course.instructor_id == fac.id) or (assignment.faculty_id == fac.id)
        if not is_assigned:
            return jsonify({"success": False, "error": "Forbidden: You are not assigned to this course/division."}), 403

    eligible_q = Student.query.options(
        db.joinedload(Student.user)
    ).join(Enrollment, Student.id == Enrollment.student_id).filter(
        Enrollment.course_id == assignment.course_id
    )
    if assignment.division and assignment.division.upper() != "ALL":
        eligible_q = eligible_q.filter(
            db.or_(Student.division == assignment.division, Student.division.is_(None))
        )
    students = eligible_q.order_by(Student.roll_number.asc(), Student.student_code.asc()).all()

    submissions_by_stu = {s.student_id: s for s in assignment.submissions}

    roster = []
    for stu in students:
        sub = submissions_by_stu.get(stu.id)
        if sub:
            sub_dict = sub.to_dict()
        else:
            sub_dict = {
                "id": None,
                "assignmentId": assignment.id,
                "studentId": stu.student_code,
                "studentName": stu.user.full_name if stu.user else None,
                "prn": stu.prn or stu.student_code,
                "rollNumber": stu.roll_number,
                "division": stu.division,
                "submissionText": None,
                "fileName": None,
                "fileExtension": None,
                "isPdf": False,
                "downloadUrl": None,
                "previewUrl": None,
                "submittedAt": None,
                "status": "not_submitted",
                "displayStatus": "Not Submitted",
                "evaluationStatus": "Awaiting Submission",
                "isEvaluated": False,
                "grade": None,
                "marks_obtained": None,
                "marks_display": None,
                "feedback": None,
            }
        roster.append(sub_dict)

    sub_count = len(assignment.submissions)
    evaluated_count = sum(1 for s in assignment.submissions if s.grade is not None or s.status in ("graded", "evaluated"))
    awaiting_count = max(0, sub_count - evaluated_count)
    counts = {
        "eligibleCount": len(students),
        "submissionsCount": sub_count,
        "evaluatedCount": evaluated_count,
        "awaitingEvaluationCount": awaiting_count,
    }
    return jsonify({
        "success": True,
        "data": {
            "assignment": assignment.to_dict(counts=counts),
            "counts": counts,
            "roster": roster,
        }
    })


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
            return jsonify({"success": False, "error": "Forbidden: You cannot access another student's submission."}), 403
    elif user.role == "faculty":
        faculty = user.faculty_profile
        assignment = submission.assignment
        is_owner = (assignment.faculty_id == faculty.id) or (assignment.course.instructor_id == faculty.id) or any(
            a.course_id == assignment.course_id for a in faculty.assignments
        )
        if not is_owner:
            return jsonify({"success": False, "error": "Forbidden: You do not have permission to view this submission."}), 403

    if submission.file_data:
        return storage_service.create_download_response(
            submission.file_data,
            submission.file_name or f"submission_{submission.id}.pdf",
            submission.mime_type,
        )

    return jsonify({"success": False, "error": "No file attached to this submission."}), 404


@bp.get("/<int:assignment_id>/submissions/<int:submission_id>/preview")
@login_required
def preview_submission(assignment_id, submission_id):
    """Inline PDF Preview for assignment evaluation."""
    from services.storage_service import storage_service
    user = current_user()
    submission = AssignmentSubmission.query.filter_by(id=submission_id, assignment_id=assignment_id).first()
    if not submission:
        return jsonify({"success": False, "error": "Submission not found."}), 404

    # Authorization
    if user.role == "student":
        student = user.student_profile
        if not student or submission.student_id != student.id:
            return jsonify({"success": False, "error": "Forbidden: You cannot access another student's submission."}), 403
    elif user.role == "faculty":
        faculty = user.faculty_profile
        assignment = submission.assignment
        is_owner = (assignment.faculty_id == faculty.id) or (assignment.course.instructor_id == faculty.id) or any(
            a.course_id == assignment.course_id for a in faculty.assignments
        )
        if not is_owner:
            return jsonify({"success": False, "error": "Forbidden: You do not have permission to view this submission."}), 403

    if not submission.file_data:
        return jsonify({"success": False, "error": "No file attached to this submission."}), 404

    fname = (submission.file_name or "").lower()
    mime = (submission.mime_type or "").lower()
    if not (fname.endswith(".pdf") or mime == "application/pdf"):
        return jsonify({
            "success": False,
            "error": "In-screen preview is only available for PDF documents. Please use the download option."
        }), 400

    return storage_service.create_preview_response(
        submission.file_data,
        submission.file_name or f"submission_{submission.id}.pdf",
        submission.mime_type or "application/pdf",
    )


@bp.get("/submissions/<int:submission_id>/download")
@login_required
def download_submission_flat(submission_id):
    """Flat URL: GET /api/assignments/submissions/<id>/download"""
    from services.storage_service import storage_service
    user = current_user()
    submission = AssignmentSubmission.query.get(submission_id)
    if not submission:
        return jsonify({"success": False, "error": "Submission not found."}), 404

    # Authorization
    if user.role == "student":
        student = user.student_profile
        if not student or submission.student_id != student.id:
            return jsonify({"success": False, "error": "Forbidden: You cannot access another student's submission."}), 403
    elif user.role == "faculty":
        faculty = user.faculty_profile
        assignment = submission.assignment
        is_owner = (assignment.faculty_id == faculty.id) or (assignment.course.instructor_id == faculty.id) or any(
            a.course_id == assignment.course_id for a in faculty.assignments
        )
        if not is_owner:
            return jsonify({"success": False, "error": "Forbidden: You do not have permission to view this submission."}), 403

    if submission.file_data:
        return storage_service.create_download_response(
            submission.file_data,
            submission.file_name or f"submission_{submission.id}.pdf",
            submission.mime_type,
        )

    return jsonify({"success": False, "error": "No file attached to this submission."}), 404


@bp.get("/submissions/<int:submission_id>/preview")
@login_required
def preview_submission_flat(submission_id):
    """Flat URL: GET /api/assignments/submissions/<id>/preview"""
    from services.storage_service import storage_service
    user = current_user()
    submission = AssignmentSubmission.query.get(submission_id)
    if not submission:
        return jsonify({"success": False, "error": "Submission not found."}), 404

    # Authorization
    if user.role == "student":
        student = user.student_profile
        if not student or submission.student_id != student.id:
            return jsonify({"success": False, "error": "Forbidden: You cannot access another student's submission."}), 403
    elif user.role == "faculty":
        faculty = user.faculty_profile
        assignment = submission.assignment
        is_owner = (assignment.faculty_id == faculty.id) or (assignment.course.instructor_id == faculty.id) or any(
            a.course_id == assignment.course_id for a in faculty.assignments
        )
        if not is_owner:
            return jsonify({"success": False, "error": "Forbidden: You do not have permission to view this submission."}), 403

    if not submission.file_data:
        return jsonify({"success": False, "error": "No file attached to this submission."}), 404

    fname = (submission.file_name or "").lower()
    mime = (submission.mime_type or "").lower()
    if not (fname.endswith(".pdf") or mime == "application/pdf"):
        return jsonify({
            "success": False,
            "error": "In-screen preview is only available for PDF documents. Please use the download option."
        }), 400

    return storage_service.create_preview_response(
        submission.file_data,
        submission.file_name or f"submission_{submission.id}.pdf",
        submission.mime_type or "application/pdf",
    )


@bp.post("/submissions/<int:submission_id>/grade")
@roles_required("faculty", "admin")
def grade_submission_flat(submission_id):
    """Flat URL: POST /api/assignments/submissions/<id>/grade"""
    user = current_user()
    data = request.get_json(silent=True) or {}

    submission = AssignmentSubmission.query.get(submission_id)
    if not submission:
        return jsonify({"success": False, "error": "Submission not found."}), 404

    # Server-side RBAC for faculty
    if user.role == "faculty":
        fac = user.faculty_profile
        assignment = submission.assignment
        is_assigned = any(
            a.course_id == assignment.course_id and (
                a.division.upper() == assignment.division.upper() or
                assignment.division.upper() == "ALL" or
                a.division.upper() == "ALL"
            )
            for a in fac.assignments
        ) or (assignment.course.instructor_id == fac.id) or (assignment.faculty_id == fac.id)
        if not is_assigned:
            return jsonify({"success": False, "error": "Forbidden: You are not authorized to grade this assignment."}), 403

    grade_val = data.get("grade") if data.get("grade") is not None else data.get("marks_obtained")
    if grade_val is None:
        return jsonify({"success": False, "error": "Marks obtained (grade) is required."}), 400

    try:
        grade_val = float(grade_val)
    except (ValueError, TypeError):
        raise ValidationError("Marks must be a valid number.")

    max_allowed = float(assignment.total_points) if assignment.total_points else 10.0
    if grade_val < 0 or grade_val > max_allowed:
        raise ValidationError(f"Marks obtained must be between 0 and {int(max_allowed)} inclusive (e.g. 0/{int(max_allowed)}, 10/{int(max_allowed)}).")

    submission.grade = grade_val
    submission.feedback = data.get("feedback")
    submission.status = "graded"
    if user.faculty_profile:
        submission.graded_by_id = user.faculty_profile.id

    db.session.commit()
    return jsonify({"success": True, "data": submission.to_dict()})


@bp.post("/<int:assignment_id>/grade")
@roles_required("faculty", "admin")
def grade_submission(assignment_id):
    user = current_user()
    data = request.get_json(silent=True) or {}

    assignment = Assignment.query.get(assignment_id)
    if not assignment:
        return jsonify({"success": False, "error": "Assignment not found."}), 404

    # Server-side RBAC for faculty
    if user.role == "faculty":
        fac = user.faculty_profile
        is_assigned = any(
            a.course_id == assignment.course_id and (
                a.division.upper() == assignment.division.upper() or
                assignment.division.upper() == "ALL" or
                a.division.upper() == "ALL"
            )
            for a in fac.assignments
        ) or (assignment.course.instructor_id == fac.id) or (assignment.faculty_id == fac.id)
        if not is_assigned:
            return jsonify({"success": False, "error": "Forbidden: You are not authorized to grade this assignment."}), 403

    # Support either submissionId directly or student lookup
    submission = None
    sub_id = data.get("submissionId") or data.get("submission_id")
    if sub_id:
        submission = AssignmentSubmission.query.filter_by(id=int(sub_id), assignment_id=assignment_id).first()

    if not submission:
        student_ref = data.get("studentId") or data.get("student_id") or data.get("prn")
        if not student_ref:
            require_fields(data, ["studentId"])

        student = Student.query.filter(
            db.or_(Student.student_code == student_ref, Student.prn == student_ref)
        ).first()
        if not student:
            return jsonify({"success": False, "error": "Student not found."}), 404

        submission = AssignmentSubmission.query.filter_by(
            assignment_id=assignment_id, student_id=student.id
        ).first()
        if not submission:
            return jsonify({"success": False, "error": "Submission not found for this student."}), 404

    grade_val = data.get("grade") if data.get("grade") is not None else data.get("marks_obtained")
    if grade_val is None:
        return jsonify({"success": False, "error": "Marks obtained (grade) is required."}), 400

    try:
        grade_val = float(grade_val)
    except (ValueError, TypeError):
        raise ValidationError("Marks must be a valid number.")

    max_allowed = float(assignment.total_points) if assignment.total_points else 10.0
    if grade_val < 0 or grade_val > max_allowed:
        raise ValidationError(f"Marks obtained must be between 0 and {int(max_allowed)} inclusive (e.g. 0/{int(max_allowed)}, 10/{int(max_allowed)}).")

    submission.grade = grade_val
    submission.feedback = data.get("feedback")
    submission.status = "graded"
    if user.faculty_profile:
        submission.graded_by_id = user.faculty_profile.id

    db.session.commit()
    return jsonify({"success": True, "data": submission.to_dict()})


@bp.put("/<int:assignment_id>")
@roles_required("faculty", "admin")
def update_assignment(assignment_id):
    assignment = Assignment.query.get(assignment_id)
    if not assignment:
        return jsonify({"success": False, "error": "Assignment not found."}), 404

    data = request.get_json(silent=True) or {}
    if "title" in data and data["title"].strip():
        assignment.title = str(data["title"]).strip()
    if "description" in data:
        assignment.description = data["description"]
    if "division" in data:
        assignment.division = str(data["division"]).strip().upper()
    if "totalPoints" in data:
        try:
            assignment.total_points = int(data["totalPoints"])
        except (ValueError, TypeError):
            pass
    if "dueDate" in data:
        try:
            assignment.due_date = datetime.fromisoformat(str(data["dueDate"]).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            raise ValidationError("Invalid due date format. Use ISO format (YYYY-MM-DDTHH:MM).")

    db.session.commit()
    return jsonify({"success": True, "data": assignment.to_dict()})


@bp.delete("/<int:assignment_id>")
@roles_required("faculty", "admin")
def delete_assignment(assignment_id):
    assignment = Assignment.query.get(assignment_id)
    if not assignment:
        return jsonify({"success": False, "error": "Assignment not found."}), 404

    db.session.delete(assignment)
    db.session.commit()
    return jsonify({"success": True, "message": "Assignment deleted."})


@bp.post("/<int:assignment_id>/submissions/<int:submission_id>/unlock")
@roles_required("admin", "faculty")
def unlock_submission(assignment_id, submission_id):
    """Module 8: Authorized HOD or Administrator grants an exceptional correction opportunity
    with mandatory reason and complete audit trail."""
    user = current_user()
    data = request.get_json(silent=True) or {}
    reason = (data.get("reason") or "").strip()
    if not reason:
        return jsonify({"success": False, "error": "A mandatory reason is required to grant an exceptional correction opportunity."}), 400

    submission = AssignmentSubmission.query.filter_by(id=submission_id, assignment_id=assignment_id).first()
    if not submission:
        return jsonify({"success": False, "error": "Submission not found."}), 404

    if user.role == "faculty":
        fac = user.faculty_profile
        is_hod = fac and fac.designation and ("hod" in fac.designation.lower() or "head" in fac.designation.lower())
        if not is_hod:
            return jsonify({"success": False, "error": "Only Head of Department (HOD) or Administrator can authorize an assignment correction opportunity."}), 403

    submission.is_locked = False
    submission.unlocked_by_id = user.id
    submission.unlocked_at = datetime.now(timezone.utc)
    submission.unlock_reason = reason
    db.session.commit()

    from models import log_audit
    log_audit(
        action="ASSIGNMENT_CORRECTION_UNLOCK",
        target_type="AssignmentSubmission",
        target_id=submission.id,
        reason=reason,
        details=f"Exceptional correction authorized by {user.role} {user.email} for student {submission.student.student_code if submission.student else None} on assignment {assignment_id}.",
        user=user
    )

    return jsonify({
        "success": True,
        "message": "Submission unlocked. Student has been granted an exceptional correction opportunity.",
        "data": submission.to_dict()
    })


