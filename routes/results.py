from datetime import datetime, timezone
from math import ceil
from flask import Blueprint, request, jsonify
from extensions import db
from models import (
    Result, AssessmentConfig, compute_grade, Student, Course, Enrollment, FacultyAssignment,
    Department, User, log_audit
)
from utils.auth import roles_required, login_required, current_user
from utils.validators import require_fields, validate_marks, ValidationError

bp = Blueprint("results", __name__, url_prefix="/api/results")


def _get_or_create_config(dept_id=None, course_id=None):
    """Retrieves specific or default institutional assessment configuration."""
    cfg = None
    if course_id:
        cfg = AssessmentConfig.query.filter_by(course_id=course_id).first()
    if not cfg and dept_id:
        cfg = AssessmentConfig.query.filter_by(department_id=dept_id, course_id=None).first()
    if not cfg:
        cfg = AssessmentConfig.query.filter_by(department_id=None, course_id=None).first()
    if not cfg:
        cfg = AssessmentConfig(
            ca1_max=20.0,
            ca2_max=20.0,
            mid_sem_max=30.0,
            end_sem_max=70.0,
            internal_weight=0.3,
            external_weight=0.7,
            min_passing_pct=40.0,
        )
        db.session.add(cfg)
        db.session.flush()
    return cfg


# =====================================================================
# 1. LIST RESULTS (Filterable by role, department, course, sem, div, status)
# =====================================================================
@bp.get("")
@login_required
def list_results():
    user = current_user()
    q = Result.query.options(
        db.joinedload(Result.student).joinedload(Student.user),
        db.joinedload(Result.student).joinedload(Student.department),
        db.joinedload(Result.course).joinedload(Course.department)
    )

    if user.role == "student":
        student = user.student_profile
        if not student:
            return jsonify({"success": True, "data": []})
        # Students can view only officially published results
        q = q.filter(Result.student_id == student.id, Result.is_published.is_(True))
    elif user.role == "faculty":
        faculty = user.faculty_profile
        if not faculty:
            return jsonify({"success": True, "data": []})
        assigned_course_ids = [a.course_id for a in faculty.assignments]
        assigned_divs = [a.division.upper() for a in faculty.assignments]

        course_code = request.args.get("courseCode")
        division = request.args.get("division")

        if course_code:
            course = Course.query.filter_by(code=course_code).first()
            if not course or course.id not in assigned_course_ids:
                return jsonify({"success": False, "error": "You are not assigned to this course."}), 403
            q = q.filter(Result.course_id == course.id)
        else:
            q = q.filter(Result.course_id.in_(assigned_course_ids) if assigned_course_ids else False)

        if division:
            div_val = division.strip().upper()
            if div_val not in assigned_divs and "ALL" not in assigned_divs:
                return jsonify({"success": False, "error": f"You are not assigned to Division {div_val}."}), 403
            q = q.join(Student).filter(Student.division == div_val)
        else:
            if "ALL" not in assigned_divs:
                q = q.join(Student).filter(Student.division.in_(assigned_divs))
    else:  # admin
        student_ref = request.args.get("studentId") or request.args.get("q")
        course_code = request.args.get("courseCode")
        dept_ref = request.args.get("department")
        sem_val = request.args.get("semester")
        division = request.args.get("division")
        status_val = request.args.get("status")

        if student_ref:
            q = q.join(Student).join(User).filter(
                db.or_(
                    Student.student_code.ilike(f"%{student_ref}%"),
                    Student.prn.ilike(f"%{student_ref}%"),
                    Student.roll_number.ilike(f"%{student_ref}%"),
                    User.full_name.ilike(f"%{student_ref}%")
                )
            )
        if course_code:
            course = Course.query.filter_by(code=course_code).first()
            q = q.filter(Result.course_id == (course.id if course else -1))
        if dept_ref and str(dept_ref).lower() != "all":
            dept = Department.resolve(dept_ref)
            if dept:
                q = q.join(Course).filter(Course.department_id == dept.id)
        if sem_val and str(sem_val).isdigit() and str(sem_val).lower() != "all":
            q = q.filter(Result.semester == int(sem_val))
        if division and str(division).lower() != "all":
            q = q.filter(Result.division.ilike(division.strip()))
        if status_val and str(status_val).lower() != "all":
            s_low = status_val.strip().lower()
            if s_low == "published":
                q = q.filter(db.or_(Result.status == "published", Result.is_published.is_(True)))
            elif s_low in ("unpublished", "draft"):
                q = q.filter(db.or_(Result.status.in_(["draft", "submitted", "under_review", "approved", "reopened"]), Result.is_published.is_(False)))
            else:
                q = q.filter(Result.status == s_low)

    results = q.order_by(Result.id.desc()).all()
    return jsonify({"success": True, "data": [r.to_dict() for r in results]})


# =====================================================================
# 2. MODULE 2: COMPLETE FACULTY MARKS ENTRY (CA1, CA2, Mid-Sem, End-Sem)
# =====================================================================
@bp.post("/marks")
@roles_required("faculty", "admin")
def enter_marks():
    """Enters or updates assessment marks (CA1, CA2, Mid-Sem, End-Sem) for a student.
    Enforces strict relational RBAC: faculty can enter marks only for assigned subjects & divisions."""
    user = current_user()
    data = request.get_json(silent=True) or {}

    stu_ref = str(data.get("studentId") or data.get("prn") or data.get("student_id") or "").strip()
    c_code = (data.get("courseCode") or data.get("course_code") or "").strip()
    if not stu_ref or not c_code:
        require_fields(data, ["studentId", "courseCode"])

    student = Student.query.filter(
        db.or_(Student.student_code == stu_ref, Student.prn == stu_ref)
    ).first()
    if not student:
        raise ValidationError(f"Student '{stu_ref}' not found.")

    course = Course.query.filter_by(code=c_code).first()
    if not course:
        raise ValidationError(f"Course '{c_code}' not found.")

    # Verify student is enrolled
    enr = Enrollment.query.filter_by(student_id=student.id, course_id=course.id).first()
    if not enr:
        return jsonify({"success": False, "error": f"Student {student.student_code} is not enrolled in course {course.code}."}), 403

    # RBAC verification for faculty
    if user.role == "faculty":
        fac = user.faculty_profile
        valid_fa = FacultyAssignment.query.filter(
            FacultyAssignment.faculty_id == fac.id,
            FacultyAssignment.course_id == course.id,
            db.or_(FacultyAssignment.division == student.division, FacultyAssignment.division.ilike("All"))
        ).first()
        if not valid_fa:
            return jsonify({
                "success": False,
                "error": f"You are not authorized to enter marks for course {course.code} Division {student.division}."
            }), 403

    # Get config for validation
    cfg = _get_or_create_config(course.department_id, course.id)

    # Locate or create Result row
    res = Result.query.filter_by(student_id=student.id, course_id=course.id).first()
    if not res:
        res = Result(
            student_id=student.id,
            course_id=course.id,
            semester=student.semester or course.semester,
            division=student.division,
            academic_year=data.get("academicYear", "2025-2026"),
            status="draft",
        )
        db.session.add(res)

    # If submitted or approved, faculty cannot modify unless authorized or reopened
    if user.role == "faculty" and res.status in ("submitted", "under_review", "approved", "published"):
        return jsonify({
            "success": False,
            "error": f"Marks are currently locked in '{res.status}' status. Editing requires reopening by administrator."
        }), 403

    # Process Assessment Entries
    # 1. CA1
    if "ca1Marks" in data or "ca1" in data:
        val = data.get("ca1Marks") if "ca1Marks" in data else data.get("ca1")
        if val is not None and str(val).strip() != "":
            max_val = float(data.get("ca1Max") or cfg.ca1_max or 20.0)
            res.ca1_marks = validate_marks(val, 0, max_val, "CA1")
            res.ca1_max = max_val
            res.ca1_status = data.get("ca1Status", "draft")

    # 2. CA2
    if "ca2Marks" in data or "ca2" in data:
        val = data.get("ca2Marks") if "ca2Marks" in data else data.get("ca2")
        if val is not None and str(val).strip() != "":
            max_val = float(data.get("ca2Max") or cfg.ca2_max or 20.0)
            res.ca2_marks = validate_marks(val, 0, max_val, "CA2")
            res.ca2_max = max_val
            res.ca2_status = data.get("ca2Status", "draft")

    # 3. Mid-Semester
    if "midSemMarks" in data or "midSem" in data or "mid_sem" in data:
        val = data.get("midSemMarks") if "midSemMarks" in data else (data.get("midSem") if "midSem" in data else data.get("mid_sem"))
        if val is not None and str(val).strip() != "":
            max_val = float(data.get("midSemMax") or cfg.mid_sem_max or 30.0)
            res.mid_sem_marks = validate_marks(val, 0, max_val, "Mid-Semester")
            res.mid_sem_max = max_val
            res.mid_sem_status = data.get("midSemStatus", "draft")

    # 4. End-Semester
    if "endSemMarks" in data or "endSem" in data or "end_sem" in data:
        val = data.get("endSemMarks") if "endSemMarks" in data else (data.get("endSem") if "endSem" in data else data.get("end_sem"))
        if val is not None and str(val).strip() != "":
            max_val = float(data.get("endSemMax") or cfg.end_sem_max or 70.0)
            res.end_sem_marks = validate_marks(val, 0, max_val, "End-Semester")
            res.end_sem_max = max_val
            res.end_sem_status = data.get("endSemStatus", "draft")

    # Attendance / Assessment status
    if "attendanceStatus" in data:
        att = str(data["attendanceStatus"]).strip().lower()
        if att in ("present", "absent", "incomplete", "withheld"):
            res.attendance_status = att

    # Action intent: save draft vs submit marks
    action_type = data.get("action", "save_draft").lower()
    now = datetime.now(timezone.utc)
    if action_type in ("submit", "submit_marks"):
        res.status = "submitted"
        res.submitted_by_id = user.id
        res.submitted_at = now
        log_audit(
            action="MARKS_SUBMIT",
            target_type="Result",
            target_id=res.id,
            details=f"Faculty {user.email} submitted marks for student {student.student_code} in course {course.code}.",
            user=user
        )
    else:
        if res.status != "reopened":
            res.status = "draft"
        log_audit(
            action="MARKS_SAVE_DRAFT",
            target_type="Result",
            target_id=res.id,
            details=f"Faculty {user.email} saved draft marks for student {student.student_code} in course {course.code}.",
            user=user
        )

    # Legacy fields sync
    res.internal_marks = res.internal_calculated
    if user.faculty_profile:
        res.entered_by_id = user.faculty_profile.id

    db.session.commit()
    return jsonify({"success": True, "message": "Marks saved successfully.", "data": res.to_dict()}), 200


@bp.post("/batch-marks")
@roles_required("faculty", "admin")
def enter_batch_marks():
    """Bulk entry for student marks across a course and division."""
    user = current_user()
    data = request.get_json(silent=True) or {}
    c_code = (data.get("courseCode") or "").strip()
    division = (data.get("division") or "A").strip().upper()
    assessment = (data.get("assessmentType") or "end_sem").lower()
    entries = data.get("entries") or []

    course = Course.query.filter_by(code=c_code).first()
    if not course:
        raise ValidationError(f"Course '{c_code}' not found.")

    # Faculty RBAC verification
    if user.role == "faculty":
        fac = user.faculty_profile
        valid_fa = FacultyAssignment.query.filter(
            FacultyAssignment.faculty_id == fac.id,
            FacultyAssignment.course_id == course.id,
            db.or_(FacultyAssignment.division == division, FacultyAssignment.division.ilike("All"))
        ).first()
        if not valid_fa:
            return jsonify({"success": False, "error": f"You are not assigned to {course.code} Division {division}."}), 403

    cfg = _get_or_create_config(course.department_id, course.id)
    saved_count = 0
    now = datetime.now(timezone.utc)
    action_type = data.get("action", "save_draft").lower()

    for item in entries:
        stu_ref = str(item.get("studentId") or item.get("prn") or "").strip()
        if not stu_ref:
            continue
        student = Student.query.filter(
            db.or_(Student.student_code == stu_ref, Student.prn == stu_ref)
        ).first()
        if not student:
            continue

        res = Result.query.filter_by(student_id=student.id, course_id=course.id).first()
        if not res:
            res = Result(
                student_id=student.id,
                course_id=course.id,
                semester=student.semester or course.semester,
                division=student.division or division,
                status="draft",
            )
            db.session.add(res)

        marks_val = item.get("marks")
        if marks_val is not None and str(marks_val).strip() != "":
            try:
                m_flt = float(marks_val)
            except (ValueError, TypeError):
                continue

            if assessment in ("ca1",):
                res.ca1_marks = min(cfg.ca1_max, max(0.0, m_flt))
                res.ca1_max = cfg.ca1_max
            elif assessment in ("ca2",):
                res.ca2_marks = min(cfg.ca2_max, max(0.0, m_flt))
                res.ca2_max = cfg.ca2_max
            elif assessment in ("mid_sem", "midsem"):
                res.mid_sem_marks = min(cfg.mid_sem_max, max(0.0, m_flt))
                res.mid_sem_max = cfg.mid_sem_max
            else:
                res.end_sem_marks = min(cfg.end_sem_max, max(0.0, m_flt))
                res.end_sem_max = cfg.end_sem_max

        if item.get("attendanceStatus"):
            res.attendance_status = item["attendanceStatus"]

        if action_type == "submit":
            res.status = "submitted"
            res.submitted_by_id = user.id
            res.submitted_at = now
        elif res.status != "reopened":
            res.status = "draft"

        res.internal_marks = res.internal_calculated
        if user.faculty_profile:
            res.entered_by_id = user.faculty_profile.id
        saved_count += 1

    db.session.commit()
    log_audit(
        action="MARKS_BATCH_UPDATE",
        target_type="Course",
        target_id=course.id,
        details=f"Batch {action_type} for {saved_count} students in {course.code} Div {division} by {user.email}.",
        user=user
    )
    return jsonify({
        "success": True,
        "message": f"Successfully processed {saved_count} student marks entries.",
        "count": saved_count
    })


# =====================================================================
# 3. MODULE 3: RESULT CONTROL AND PUBLISHING LIFECYCLE
# (Draft -> Submitted -> Under Review -> Approved -> Published / Reopened)
# =====================================================================
@bp.post("/batch-status")
@roles_required("admin", "faculty")
def transition_batch_status():
    """Transition status of examination results for a course and division."""
    user = current_user()
    data = request.get_json(silent=True) or {}
    c_code = (data.get("courseCode") or "").strip()
    division = (data.get("division") or "").strip().upper()
    target_status = (data.get("status") or "").strip().lower()
    reason = (data.get("reason") or "").strip()

    valid_statuses = ("submitted", "under_review", "approved", "published", "reopened", "rejected")
    if target_status not in valid_statuses:
        raise ValidationError(f"Invalid status transition target: '{target_status}'.")

    course = Course.query.filter_by(code=c_code).first()
    if not course:
        raise ValidationError(f"Course '{c_code}' not found.")

    # Permissions check
    if target_status in ("approved", "published") and user.role != "admin":
        return jsonify({"success": False, "error": "Only authorized administrators can approve and publish results."}), 403

    if target_status == "reopened":
        if user.role != "admin":
            return jsonify({"success": False, "error": "Only authorized administrators can reopen finalized results."}), 403
        if not reason:
            return jsonify({"success": False, "error": "A mandatory reason is strictly required to reopen results."}), 400

    q = Result.query.filter_by(course_id=course.id)
    if division and division != "ALL":
        q = q.join(Student).filter(Student.division == division)

    results = q.all()
    if not results:
        return jsonify({"success": False, "error": "No results found for this course and division."}), 404

    now = datetime.now(timezone.utc)
    for r in results:
        if target_status == "submitted":
            r.status = "submitted"
            r.submitted_by_id = user.id
            r.submitted_at = now
        elif target_status == "under_review":
            r.status = "under_review"
            r.reviewed_by_id = user.id
            r.reviewed_at = now
        elif target_status == "approved":
            r.status = "approved"
            r.approved_by_id = user.id
            r.approved_at = now
        elif target_status == "published":
            r.status = "published"
            r.is_published = True
            r.published_by_id = user.id
            r.published_at = now
        elif target_status in ("reopened", "rejected"):
            r.status = "reopened"
            r.is_published = False
            r.reopened_by_id = user.id
            r.reopened_at = now
            r.reopen_reason = reason

    db.session.commit()
    log_audit(
        action=f"RESULT_LIFECYCLE_{target_status.upper()}",
        target_type="Course",
        target_id=course.id,
        reason=reason or None,
        details=f"Transitioned {len(results)} results for {course.code} Div {division or 'All'} to '{target_status}'.",
        user=user
    )

    return jsonify({
        "success": True,
        "message": f"Successfully transitioned {len(results)} results to '{target_status}'.",
        "count": len(results)
    })


# =====================================================================
# 4. MODULE 4: ADMIN STUDENT RESULT CARD
# =====================================================================
@bp.get("/card/<string:student_ref>")
@login_required
def get_student_result_card(student_ref):
    """Module 4: Complete Admin Student Result Card with subject-wise assessment breakdown,
    internal/external totals, percentage, grade, credits, and publication timestamp."""
    user = current_user()
    q_filters = [Student.student_code == student_ref, Student.prn == student_ref]
    if student_ref.isdigit():
        q_filters.append(Student.id == int(student_ref))
    student = Student.query.join(User).filter(
        db.or_(*q_filters, User.email.ilike(student_ref))
    ).first()
    if not student:
        return jsonify({"success": False, "error": f"Student '{student_ref}' not found."}), 404

    # Authorization: student can only view own result card
    if user.role == "student" and user.student_profile.id != student.id:
        return jsonify({"success": False, "error": "Forbidden: you can only access your own result card."}), 403

    # Query student results
    q = Result.query.filter_by(student_id=student.id).options(
        db.joinedload(Result.course)
    )
    # Students view ONLY published results; Administrators can view unpublished (with clear flag)
    if user.role == "student":
        q = q.filter(Result.is_published.is_(True))

    results = q.all()

    # Aggregate calculations
    total_obtained = sum(r.total_marks for r in results)
    total_possible = sum(r.total_max_marks for r in results)
    overall_pct = round((total_obtained / total_possible) * 100.0, 2) if total_possible > 0 else 0.0
    overall_grade = compute_grade(overall_pct)
    passed_all = all(r.is_passed for r in results) if results else False
    backlogs_count = sum(1 for r in results if not r.is_passed)

    has_unpublished = any(not r.is_published for r in results)
    result_status = "PASSED" if (passed_all and results) else ("FAIL" if results else "AWAITING RESULTS")

    card_data = {
        "institution": {
            "name": "Sharad Institute of Technology College of Engineering",
            "shortName": "SITCOE, Yadrav",
            "tagline": "Autonomous Institute Affiliated to DBATU",
            "logoUrl": "images/sitcoe_logo.png",
        },
        "student": {
            "id": student.id,
            "studentCode": student.student_code,
            "prn": student.prn or student.student_code,
            "rollNumber": student.roll_number,
            "name": student.user.full_name,
            "email": student.user.email,
            "department": student.department.name if student.department else None,
            "departmentCode": student.department.code if student.department else None,
            "semester": student.semester,
            "division": student.division,
            "year": student.year_label,
            "academicYear": results[0].academic_year if results else "2025-2026",
        },
        "subjects": [r.to_dict() for r in results],
        "summary": {
            "totalSubjects": len(results),
            "totalCredits": sum(r.course.credits for r in results if r.course and r.is_passed),
            "maxCredits": sum(r.course.credits for r in results if r.course),
            "aggregateMarks": round(total_obtained, 2),
            "maximumMarks": round(total_possible, 2),
            "percentage": overall_pct,
            "grade": overall_grade,
            "resultStatus": result_status,
            "backlogsCount": backlogs_count,
            "isPublished": not has_unpublished if results else False,
            "hasUnpublishedRecords": has_unpublished,
            "publishedAt": (max((r.published_at for r in results if r.published_at), default=None).isoformat() if any(r.published_at for r in results) else None) if results else None,
        }
    }

    if user.role == "admin" and has_unpublished:
        log_audit(
            action="UNPUBLISHED_RESULT_ACCESS",
            target_type="Student",
            target_id=student.id,
            details=f"Admin {user.email} inspected unpublished result card for student {student.student_code}.",
            user=user
        )

    return jsonify({"success": True, "data": card_data})


# =====================================================================
# 5. MODULE 5: TOPPERS AND MERIT LIST
# =====================================================================
@bp.get("/toppers")
@login_required
def get_toppers_and_merit_list():
    """Module 5: Dynamic calculation of Toppers and Merit List based strictly on finalized,
    officially published database records."""
    dept_ref = request.args.get("department")
    sem_val = request.args.get("semester")
    limit = min(50, max(1, int(request.args.get("limit", 10))))
    search = (request.args.get("q") or "").strip().lower()

    # Query only published results
    q = db.session.query(
        Student,
        db.func.sum(Result.internal_marks + Result.end_sem_marks).label("total_marks"),
        db.func.count(Result.id).label("subject_count"),
        db.func.avg((Result.internal_marks + Result.end_sem_marks)).label("avg_marks")
    ).join(
        Result, Student.id == Result.student_id
    ).filter(
        Result.is_published.is_(True)
    )

    if dept_ref:
        dept = Department.resolve(dept_ref)
        if dept:
            q = q.filter(Student.department_id == dept.id)
    if sem_val and str(sem_val).isdigit():
        q = q.filter(Student.semester == int(sem_val))

    q = q.group_by(Student.id).order_by(db.desc("total_marks"), db.desc("avg_marks"))
    ranked = q.all()

    merit_list = []
    rank = 1
    for stu, tot_marks, sub_count, avg_m in ranked:
        tot_flt = round(float(tot_marks or 0.0), 2)
        pct = round(tot_flt / (sub_count * 100.0) * 100.0, 2) if sub_count else 0.0
        item = {
            "rank": rank,
            "studentId": stu.student_code,
            "prn": stu.prn or stu.student_code,
            "name": stu.user.full_name,
            "rollNumber": stu.roll_number,
            "department": stu.department.name if stu.department else "General",
            "departmentCode": stu.department.code if stu.department else "GEN",
            "semester": stu.semester,
            "division": stu.division,
            "totalMarks": tot_flt,
            "maxMarks": sub_count * 100,
            "percentage": pct,
            "status": "PASSED" if pct >= 40.0 else "FAIL",
            "grade": compute_grade(pct)
        }
        if not search or search in item["name"].lower() or search in str(item["rollNumber"]).lower() or search in item["prn"].lower():
            merit_list.append(item)
            rank += 1
            if len(merit_list) >= limit:
                break

    return jsonify({"success": True, "data": merit_list, "count": len(merit_list)})


# =====================================================================
# 6. MODULE 6: RESULT ANALYTICS AND PASS PERCENTAGE
# =====================================================================
@bp.get("/analytics")
@login_required
def get_result_analytics():
    """Module 6: Examination Analytics Dashboard calculating pass percentages,
    grade distribution, and subject averages strictly from live database records."""
    dept_ref = request.args.get("department")
    sem_val = request.args.get("semester")
    course_code = request.args.get("courseCode")

    q = Result.query.join(Student).join(Course)

    if dept_ref:
        dept = Department.resolve(dept_ref)
        if dept:
            q = q.filter(Course.department_id == dept.id)
    if sem_val and str(sem_val).isdigit():
        sem_int = int(sem_val)
        q = q.filter(db.or_(Result.semester == sem_int, Course.semester == sem_int, Student.semester == sem_int))
    if course_code:
        q = q.filter(Course.code == course_code)

    all_res = q.all()
    total_records = len(all_res)

    published_res = [r for r in all_res if r.is_published]
    pub_count = len(published_res)
    unpub_count = total_records - pub_count

    # Passed / Failed on published
    passed_count = sum(1 for r in published_res if r.is_passed)
    failed_count = sum(1 for r in published_res if not r.is_passed and r.attendance_status == "present")
    absent_count = sum(1 for r in published_res if r.attendance_status == "absent")
    withheld_count = sum(1 for r in published_res if r.attendance_status == "withheld")
    incomplete_count = sum(1 for r in published_res if r.attendance_status == "incomplete")

    pass_pct = round((passed_count / pub_count) * 100.0, 1) if pub_count > 0 else 0.0

    scores = [r.total_marks for r in published_res]
    highest = max(scores, default=0.0)
    lowest = min(scores, default=0.0)
    average = round(sum(scores) / len(scores), 1) if scores else 0.0

    # Grade distribution
    grades = {"A+": 0, "A": 0, "B+": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    for r in published_res:
        g = r.grade
        if g in grades:
            grades[g] += 1

    return jsonify({
        "success": True,
        "data": {
            "totalEvaluated": total_records,
            "publishedCount": pub_count,
            "unpublishedCount": unpub_count,
            "passedCount": passed_count,
            "failedCount": failed_count,
            "absentCount": absent_count,
            "withheldCount": withheld_count,
            "incompleteCount": incomplete_count,
            "passPercentage": pass_pct,
            "highestMarks": highest,
            "lowestMarks": lowest,
            "averageMarks": average,
            "gradeDistribution": grades,
        }
    })


# =====================================================================
# 7. MODULE 7: STUDENT PERFORMANCE HISTORY
# =====================================================================
@bp.get("/history/<string:student_ref>")
@login_required
def get_student_academic_history(student_ref):
    """Module 7: Multi-semester historical academic progression and backlog tracking."""
    user = current_user()
    student = Student.query.filter(
        db.or_(Student.student_code == student_ref, Student.prn == student_ref)
    ).first()
    if not student:
        return jsonify({"success": False, "error": "Student not found."}), 404

    if user.role == "student" and user.student_profile.id != student.id:
        return jsonify({"success": False, "error": "Forbidden: cannot view others' performance history."}), 403

    q = Result.query.filter_by(student_id=student.id).options(
        db.joinedload(Result.course)
    )
    if user.role == "student":
        q = q.filter(Result.is_published.is_(True))

    results = q.order_by(Result.semester.asc(), Result.id.asc()).all()

    # Group by semester
    semesters_map = {}
    for r in results:
        sem_key = f"Semester {r.semester or 1}"
        if sem_key not in semesters_map:
            semesters_map[sem_key] = []
        semesters_map[sem_key].append(r.to_dict())

    history = []
    for sem_label, list_res in semesters_map.items():
        tot_obt = sum(r["total"] for r in list_res)
        tot_max = sum(r["maxTotal"] for r in list_res)
        pct = round((tot_obt / tot_max) * 100.0, 2) if tot_max > 0 else 0.0
        history.append({
            "semester": sem_label,
            "subjects": list_res,
            "totalMarks": round(tot_obt, 2),
            "maxMarks": round(tot_max, 2),
            "percentage": pct,
            "sgpa": round(pct / 10.0, 2),
            "backlogs": sum(1 for r in list_res if not r["isPassed"])
        })

    return jsonify({"success": True, "data": history, "student": student.to_dict()})


# =====================================================================
# 8. ASSESSMENT CONFIGURATION & AUDIT ROUTES
# =====================================================================
@bp.get("/config")
@roles_required("admin")
def get_config():
    dept_id = request.args.get("departmentId")
    course_id = request.args.get("courseId")
    cfg = _get_or_create_config(dept_id, course_id)
    return jsonify({"success": True, "data": cfg.to_dict()})


@bp.put("/config")
@roles_required("admin")
def update_config():
    data = request.get_json(silent=True) or {}
    dept_id = data.get("departmentId")
    course_id = data.get("courseId")
    cfg = _get_or_create_config(dept_id, course_id)

    if "ca1Max" in data:
        cfg.ca1_max = float(data["ca1Max"])
    if "ca2Max" in data:
        cfg.ca2_max = float(data["ca2Max"])
    if "midSemMax" in data:
        cfg.mid_sem_max = float(data["midSemMax"])
    if "endSemMax" in data:
        cfg.end_sem_max = float(data["endSemMax"])
    if "minPassingPct" in data:
        cfg.min_passing_pct = float(data["minPassingPct"])

    db.session.commit()
    log_audit(
        action="ASSESSMENT_CONFIG_UPDATE",
        target_type="AssessmentConfig",
        target_id=cfg.id,
        details=f"Admin {current_user().email} updated assessment configuration parameters.",
        user=current_user()
    )
    return jsonify({"success": True, "data": cfg.to_dict()})


# =====================================================================
# 9. REAL-WORLD CONTROLLER OF EXAMINATIONS (COE) RESULT CONTROL SUITE
# =====================================================================

@bp.get("/my")
@login_required
def get_my_results():
    """Personal published examination results ledger for enrolled students."""
    user = current_user()
    if user.role != "student":
        return jsonify({"success": False, "error": "Only students have personal results ledger."}), 403
    student = user.student_profile
    if not student:
        return jsonify({"success": True, "data": []})
    q = Result.query.filter_by(student_id=student.id, is_published=True).options(
        db.joinedload(Result.course).joinedload(Course.department)
    ).order_by(Result.semester.asc(), Result.id.asc()).all()
    return jsonify({"success": True, "data": [r.to_dict() for r in q]})


@bp.route("/<int:result_id>/publish", methods=["POST", "PUT"])
@roles_required("admin")
def publish_individual_result(result_id):
    """Immediate publication of a single student scorecard by CoE."""
    user = current_user()
    res = db.session.get(Result, result_id)
    if not res:
        return jsonify({"success": False, "error": f"Result #{result_id} not found."}), 404

    now = datetime.now(timezone.utc)
    res.is_published = True
    res.status = "published"
    res.published_by_id = user.id
    res.published_at = now
    db.session.commit()

    log_audit(
        action="RESULT_PUBLISH_INDIVIDUAL",
        target_type="Result",
        target_id=res.id,
        details=f"Admin {user.email} published individual result for student {res.student.student_code if res.student else res.student_id} in {res.course.code if res.course else res.course_id}.",
        user=user
    )
    return jsonify({
        "success": True,
        "message": "Result successfully published to student portal.",
        "data": res.to_dict()
    })


@bp.route("/<int:result_id>/withhold", methods=["POST", "PUT"])
@roles_required("admin")
def withhold_individual_result(result_id):
    """Withhold or revoke publication of a single student scorecard (e.g. pending dues or discipline)."""
    user = current_user()
    res = db.session.get(Result, result_id)
    if not res:
        return jsonify({"success": False, "error": f"Result #{result_id} not found."}), 404

    data = request.get_json(silent=True) or {}
    reason = (data.get("reason") or "Withheld by Controller of Examinations").strip()

    now = datetime.now(timezone.utc)
    res.is_published = False
    res.attendance_status = "withheld"
    res.reopened_by_id = user.id
    res.reopened_at = now
    res.reopen_reason = reason
    db.session.commit()

    log_audit(
        action="RESULT_WITHHOLD_INDIVIDUAL",
        target_type="Result",
        target_id=res.id,
        reason=reason,
        details=f"Admin {user.email} withheld result for student {res.student.student_code if res.student else res.student_id} in {res.course.code if res.course else res.course_id}.",
        user=user
    )
    return jsonify({
        "success": True,
        "message": "Result successfully withheld from student portal.",
        "data": res.to_dict()
    })


@bp.route("/<int:result_id>/override", methods=["POST", "PUT"])
@roles_required("admin")
def override_student_marks(result_id):
    """Authoritative Controller of Examinations marks amendment, grievance adjustment & audit logging."""
    user = current_user()
    res = db.session.get(Result, result_id)
    if not res:
        return jsonify({"success": False, "error": f"Result #{result_id} not found."}), 404

    data = request.get_json(silent=True) or {}
    reason = (data.get("reason") or "").strip()
    if not reason:
        return jsonify({"success": False, "error": "A mandatory administrative audit reason is required for marks override."}), 400

    cfg = _get_or_create_config(res.course.department_id if res.course else None, res.course_id)
    old_ca1 = res.ca1_marks
    old_ca2 = res.ca2_marks
    old_mid = res.mid_sem_marks
    old_end = res.end_sem_marks
    old_att = res.attendance_status
    old_tot = res.total_marks
    old_grade = res.grade

    # Update CA1
    if "ca1" in data or "ca1Marks" in data:
        v = data.get("ca1") if "ca1" in data else data.get("ca1Marks")
        if v is not None and str(v).strip() != "":
            res.ca1_marks = min(cfg.ca1_max, max(0.0, float(v)))
            res.ca1_status = "approved"

    # Update CA2
    if "ca2" in data or "ca2Marks" in data:
        v = data.get("ca2") if "ca2" in data else data.get("ca2Marks")
        if v is not None and str(v).strip() != "":
            res.ca2_marks = min(cfg.ca2_max, max(0.0, float(v)))
            res.ca2_status = "approved"

    # Update Mid-Sem
    if "midSem" in data or "midSemMarks" in data:
        v = data.get("midSem") if "midSem" in data else data.get("midSemMarks")
        if v is not None and str(v).strip() != "":
            res.mid_sem_marks = min(cfg.mid_sem_max, max(0.0, float(v)))
            res.mid_sem_status = "approved"

    # Update End-Sem
    if "endSem" in data or "endSemMarks" in data:
        v = data.get("endSem") if "endSem" in data else data.get("endSemMarks")
        if v is not None and str(v).strip() != "":
            res.end_sem_marks = min(cfg.end_sem_max, max(0.0, float(v)))
            res.end_sem_status = "approved"

    # Update Attendance Status
    if "attendanceStatus" in data:
        att = str(data["attendanceStatus"]).strip().lower()
        if att in ("present", "absent", "incomplete", "withheld"):
            res.attendance_status = att

    # Update Publication Status
    if "isPublished" in data:
        pub_flag = bool(data["isPublished"])
        res.is_published = pub_flag
        if pub_flag:
            res.status = "published"
            res.published_by_id = user.id
            res.published_at = datetime.now(timezone.utc)
        elif res.status == "published":
            res.status = "approved"

    if "status" in data:
        s_val = str(data["status"]).strip().lower()
        if s_val in ("draft", "submitted", "under_review", "approved", "published", "reopened"):
            res.status = s_val

    # Recalculate legacy sync
    res.internal_marks = res.internal_calculated
    res.reopen_reason = f"CoE Override: {reason}"
    res.reopened_by_id = user.id
    res.reopened_at = datetime.now(timezone.utc)

    db.session.commit()

    log_audit(
        action="MARKS_OVERRIDE_ADMIN",
        target_type="Result",
        target_id=res.id,
        reason=reason,
        details=(
            f"Admin {user.email} overridden marks for student {res.student.student_code if res.student else res.student_id} in {res.course.code if res.course else res.course_id}. "
            f"Scores: [CA1: {old_ca1}->{res.ca1_marks}, CA2: {old_ca2}->{res.ca2_marks}, Mid: {old_mid}->{res.mid_sem_marks}, End: {old_end}->{res.end_sem_marks}]. "
            f"Total: {old_tot}->{res.total_marks}, Grade: {old_grade}->{res.grade}. Reason: {reason}"
        ),
        user=user
    )

    return jsonify({
        "success": True,
        "message": f"Successfully updated and audited result for {res.student.user.full_name if (res.student and res.student.user) else 'student'}.",
        "data": res.to_dict()
    })


@bp.post("/bulk-publish")
@roles_required("admin")
def bulk_publish_results():
    """Bulk declaration or revocation of results for an entire semester or department."""
    user = current_user()
    data = request.get_json(silent=True) or {}
    dept_ref = data.get("department")
    sem_val = data.get("semester")
    course_code = data.get("courseCode")
    action = (data.get("action") or "publish").strip().lower()
    reason = (data.get("reason") or "").strip()

    if action == "reopen" and not reason:
        return jsonify({"success": False, "error": "Mandatory audit reason required when reopening results."}), 400

    q = Result.query.join(Student).join(Course)

    if dept_ref and str(dept_ref).lower() != "all":
        dept = Department.resolve(dept_ref)
        if dept:
            q = q.filter(Course.department_id == dept.id)

    if sem_val and str(sem_val).lower() != "all" and str(sem_val).isdigit():
        q = q.filter(Result.semester == int(sem_val))

    if course_code and str(course_code).lower() != "all":
        q = q.filter(Course.code == course_code.strip())

    results = q.all()
    if not results:
        return jsonify({"success": False, "error": "No examination results match the specified criteria."}), 404

    now = datetime.now(timezone.utc)
    updated_count = 0

    for r in results:
        if action == "publish":
            r.is_published = True
            r.status = "published"
            r.published_by_id = user.id
            r.published_at = now
            updated_count += 1
        elif action == "unpublish":
            r.is_published = False
            if r.status == "published":
                r.status = "approved"
            updated_count += 1
        elif action == "approve":
            r.status = "approved"
            r.approved_by_id = user.id
            r.approved_at = now
            updated_count += 1
        elif action == "reopen":
            r.is_published = False
            r.status = "reopened"
            r.reopened_by_id = user.id
            r.reopened_at = now
            r.reopen_reason = reason
            updated_count += 1

    db.session.commit()
    log_audit(
        action=f"BULK_RESULT_{action.upper()}",
        target_type="ExamBatch",
        target_id=0,
        reason=reason or None,
        details=f"Admin {user.email} executed bulk {action} on {updated_count} results (Dept: {dept_ref}, Sem: {sem_val}, Course: {course_code}).",
        user=user
    )

    action_label = {
        "publish": "published to student portals",
        "unpublish": "withheld / hidden from student portals",
        "approve": "approved for declaration",
        "reopen": "reopened for faculty amendment"
    }.get(action, action)

    return jsonify({
        "success": True,
        "message": f"Successfully {action_label} for {updated_count} student examination records.",
        "count": updated_count
    })


@bp.post("/apply-grace")
@roles_required("admin")
def apply_grace_marks():
    """Awards institutional moderation grace marks for borderline failing students per autonomous ordinance."""
    user = current_user()
    data = request.get_json(silent=True) or {}
    dept_ref = data.get("department")
    sem_val = data.get("semester")
    course_code = data.get("courseCode")
    max_grace = float(data.get("maxGraceMarks") or 3.0)
    reason = (data.get("reason") or "Ordinance 4.2 Standing Committee Moderation Grace Marks").strip()

    q = Result.query.join(Student).join(Course).filter(
        Result.attendance_status == "present"
    )

    if dept_ref and str(dept_ref).lower() != "all":
        dept = Department.resolve(dept_ref)
        if dept:
            q = q.filter(Course.department_id == dept.id)

    if sem_val and str(sem_val).lower() != "all" and str(sem_val).isdigit():
        q = q.filter(Result.semester == int(sem_val))

    if course_code and str(course_code).lower() != "all":
        q = q.filter(Course.code == course_code.strip())

    results = q.all()
    awarded_list = []

    for r in results:
        if not r.is_passed:
            passing_cutoff = (r.total_max_marks * 0.40)
            deficit = passing_cutoff - r.total_marks
            if 0 < deficit <= max_grace:
                old_tot = r.total_marks
                r.end_sem_marks = round((r.end_sem_marks or 0.0) + deficit, 2)
                r.reopen_reason = f"Passed with Grace Marks (+{round(deficit, 1)} pts): {reason}"
                r.status = "approved"
                awarded_list.append({
                    "id": r.id,
                    "studentName": r.student.user.full_name if (r.student and r.student.user) else r.student_id,
                    "prn": r.student.prn if r.student else None,
                    "courseCode": r.course.code if r.course else None,
                    "oldTotal": old_tot,
                    "graceAwarded": round(deficit, 1),
                    "newTotal": r.total_marks,
                    "newGrade": r.grade,
                    "isPassed": r.is_passed
                })

    if awarded_list:
        db.session.commit()
        log_audit(
            action="MODERATION_GRACE_MARKS_APPLIED",
            target_type="ExamBatch",
            target_id=0,
            reason=reason,
            details=f"Admin {user.email} awarded grace marks to {len(awarded_list)} qualifying borderline students.",
            user=user
        )

    return jsonify({
        "success": True,
        "message": f"Evaluated eligible candidates. Awarded grace marks to {len(awarded_list)} student scorecards.",
        "awardedCount": len(awarded_list),
        "data": awarded_list
    })


@bp.get("/gazette")
@login_required
def get_examination_gazette():
    """Generates complete institutional broadsheet ledger with course-by-course breakdowns and statistical analysis."""
    dept_ref = request.args.get("department")
    sem_val = request.args.get("semester")
    acad_year = request.args.get("academicYear", "2025-2026")

    dept = None
    if dept_ref and str(dept_ref).lower() != "all":
        dept = Department.resolve(dept_ref)

    sem_int = int(sem_val) if (sem_val and str(sem_val).isdigit()) else None

    c_q = Course.query.options(db.joinedload(Course.department))
    if dept:
        c_q = c_q.filter(Course.department_id == dept.id)
    if sem_int:
        c_q = c_q.filter(Course.semester == sem_int)
    courses = c_q.order_by(Course.code.asc()).all()

    r_q = Result.query.join(Student).join(Course).options(
        db.joinedload(Result.student).joinedload(Student.user),
        db.joinedload(Result.student).joinedload(Student.department),
        db.joinedload(Result.course)
    )
    if dept:
        r_q = r_q.filter(Course.department_id == dept.id)
    if sem_int:
        r_q = r_q.filter(db.or_(Result.semester == sem_int, Course.semester == sem_int, Student.semester == sem_int))

    results = r_q.all()

    students_map = {}
    for r in results:
        stu = r.student
        if not stu:
            continue
        sid = stu.id
        if sid not in students_map:
            students_map[sid] = {
                "student": {
                    "id": stu.id,
                    "studentCode": stu.student_code,
                    "prn": stu.prn or stu.student_code,
                    "rollNumber": stu.roll_number,
                    "name": stu.user.full_name if stu.user else "Student",
                    "department": stu.department.name if stu.department else (dept.name if dept else "General"),
                    "departmentCode": stu.department.code if stu.department else (dept.code if dept else "GEN"),
                    "semester": stu.semester or sem_int,
                    "division": stu.division or "A"
                },
                "courses": {},
                "totalObtained": 0.0,
                "totalMax": 0.0,
                "totalCredits": 0,
                "earnedCredits": 0,
                "backlogs": 0,
                "hasUnpublished": False,
                "allPassed": True
            }

        c_code = r.course.code if r.course else "COURSE"
        c_credits = (r.course.credits if r.course else 3) or 3

        students_map[sid]["courses"][c_code] = {
            "ca1": r.ca1_marks,
            "ca2": r.ca2_marks,
            "midSem": r.mid_sem_marks,
            "endSem": r.end_sem_marks,
            "internal": r.internal_calculated,
            "total": r.total_marks,
            "max": r.total_max_marks,
            "grade": r.grade,
            "isPassed": r.is_passed,
            "attendanceStatus": r.attendance_status,
            "isPublished": r.is_published
        }

        students_map[sid]["totalObtained"] += r.total_marks
        students_map[sid]["totalMax"] += r.total_max_marks
        students_map[sid]["totalCredits"] += c_credits
        if r.is_passed:
            students_map[sid]["earnedCredits"] += c_credits
        else:
            students_map[sid]["backlogs"] += 1
            students_map[sid]["allPassed"] = False

        if not r.is_published:
            students_map[sid]["hasUnpublished"] = True

    roster = []
    distinction_count = 0
    first_class_count = 0
    second_class_count = 0
    pass_class_count = 0
    fail_count = 0

    for sid, entry in students_map.items():
        tot_obt = round(entry["totalObtained"], 2)
        tot_max = round(entry["totalMax"], 2)
        pct = round((tot_obt / tot_max) * 100.0, 2) if tot_max > 0 else 0.0
        sgpa = round(pct / 10.0, 2)

        if entry["allPassed"] and len(entry["courses"]) > 0:
            if pct >= 75.0:
                classification = "FIRST CLASS WITH DISTINCTION"
                distinction_count += 1
            elif pct >= 60.0:
                classification = "FIRST CLASS"
                first_class_count += 1
            elif pct >= 50.0:
                classification = "SECOND CLASS"
                second_class_count += 1
            else:
                classification = "PASS CLASS"
                pass_class_count += 1
            final_result = "PASS"
        else:
            classification = "FAIL / ATKT" if entry["backlogs"] <= 3 else "FAIL"
            final_result = "ATKT" if (0 < entry["backlogs"] <= 3) else "FAIL"
            fail_count += 1

        roster.append({
            "student": entry["student"],
            "courseScores": entry["courses"],
            "totalMarks": tot_obt,
            "maxMarks": tot_max,
            "percentage": pct,
            "sgpa": sgpa,
            "earnedCredits": entry["earnedCredits"],
            "totalCredits": entry["totalCredits"],
            "backlogs": entry["backlogs"],
            "classification": classification,
            "finalResult": final_result,
            "hasUnpublished": entry["hasUnpublished"]
        })

    roster.sort(key=lambda s: (str(s["student"]["rollNumber"] or "999999"), str(s["student"]["prn"] or "")))

    total_appeared = len(roster)
    total_passed = total_appeared - fail_count
    pass_rate = round((total_passed / total_appeared) * 100.0, 1) if total_appeared > 0 else 0.0

    return jsonify({
        "success": True,
        "data": {
            "institution": {
                "name": "Sharad Institute of Technology College of Engineering",
                "autonomous": "An Autonomous Institute Affiliated to DBATU",
                "coe": "Office of the Controller of Examinations",
                "gazetteTitle": "Official Autonomous Examination Gazette & Broadsheet",
                "academicYear": acad_year,
                "department": dept.name if dept else "All Engineering Departments",
                "departmentCode": dept.code if dept else "ALL",
                "semester": f"Semester {sem_int}" if sem_int else "All Semesters",
                "generatedAt": datetime.now(timezone.utc).strftime("%d-%b-%Y %H:%M UTC")
            },
            "courses": [c.to_dict() for c in courses],
            "statistics": {
                "totalAppeared": total_appeared,
                "totalPassed": total_passed,
                "totalFailed": fail_count,
                "passPercentage": pass_rate,
                "distinctionCount": distinction_count,
                "firstClassCount": first_class_count,
                "secondClassCount": second_class_count,
                "passClassCount": pass_class_count
            },
            "roster": roster,
            "students": roster
        }
    })
