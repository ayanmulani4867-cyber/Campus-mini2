from datetime import date
from flask import Blueprint, request, jsonify
from extensions import db
from models import (
    Student, Course, AttendanceSession, AttendanceRecord, Enrollment, FacultyAssignment, Faculty,
)
from utils.auth import roles_required, login_required, current_user
from utils.validators import require_fields, ValidationError

bp = Blueprint("attendance", __name__, url_prefix="/api/attendance")


def _status_label(pct):
    if pct >= 85:
        return "Excellent"
    if pct >= 75:
        return "Good"
    return "Shortage Warning"


@bp.get("/summary")
@login_required
def attendance_summary():
    """Subject-wise Held/Attended/Percentage table with detailed counts and history.
    Students see their own; faculty/admin can pass ?studentId=STU..."""
    from flask import current_app
    user = current_user()
    if user.role == "student":
        student = user.student_profile
        if not student:
            student = Student.query.filter_by(user_id=user.id).first()
        if not student:
            return jsonify({"success": False, "error": "Student profile not found."}), 404
    else:
        code = request.args.get("studentId")
        if not code:
            raise ValidationError("studentId is required for faculty/admin lookups.")
        student = Student.query.filter(
            db.or_(Student.student_code == code, Student.prn == code)
        ).first()
        if not student:
            return jsonify({"success": False, "error": "Student not found."}), 404

    # Configurable Late attendance policy (default 1.0 = counted as attended, 0.5 = half attendance)
    late_weight = float(current_app.config.get("LATE_ATTENDANCE_WEIGHT", 1.0))

    # 1. Courses from explicit enrollments
    enrollments = (
        Enrollment.query.options(
            db.joinedload(Enrollment.course).joinedload(Course.instructor).joinedload(Faculty.user)
        )
        .filter_by(student_id=student.id)
        .all()
    )
    enr_courses = [enr.course for enr in enrollments if enr.course]

    # 2. Courses matching student's department and semester
    dept_courses = (
        Course.query.options(
            db.joinedload(Course.instructor).joinedload(Faculty.user)
        )
        .filter_by(department_id=student.department_id, semester=student.semester, status="active")
        .all()
    )

    # 3. Fetch all attendance records for this student in a single query with sessions and markers eager-loaded
    all_records = (
        AttendanceRecord.query.options(
            db.joinedload(AttendanceRecord.session).joinedload(AttendanceSession.marked_by).joinedload(Faculty.user),
            db.joinedload(AttendanceRecord.session).joinedload(AttendanceSession.course).joinedload(Course.instructor).joinedload(Faculty.user)
        )
        .join(AttendanceSession, AttendanceRecord.session_id == AttendanceSession.id)
        .filter(AttendanceRecord.student_id == student.id)
        .order_by(AttendanceSession.session_date.desc())
        .all()
    )

    records_by_course = {}
    record_courses = []
    for r in all_records:
        if r.session and r.session.course_id:
            records_by_course.setdefault(r.session.course_id, []).append(r)
            if r.session.course:
                record_courses.append(r.session.course)

    # Merge distinct courses: enrollments first, then department semester courses, then any other attended courses
    courses = []
    seen_ids = set()
    for c in enr_courses + dept_courses + record_courses:
        if c and c.id not in seen_ids:
            seen_ids.add(c.id)
            courses.append(c)

    rows = []
    total_held = total_attended = 0
    total_present = total_absent = total_late = 0

    for course in courses:
        records = records_by_course.get(course.id, [])
        held = len(records)
        present_count = sum(1 for r in records if r.status == "present")
        absent_count = sum(1 for r in records if r.status == "absent")
        late_count = sum(1 for r in records if r.status == "late")
        attended = round(present_count + (late_count * late_weight), 1)
        pct = round((attended / held) * 100, 1) if held else 0.0

        total_held += held
        total_attended += attended
        total_present += present_count
        total_absent += absent_count
        total_late += late_count

        rows.append({
            "courseCode": course.code,
            "courseTitle": course.title,
            "courseName": course.title,
            "instructor": course.instructor.user.full_name if (course.instructor and course.instructor.user) else None,
            "held": held,
            "totalConducted": held,
            "attended": attended,
            "presentCount": present_count,
            "absentCount": absent_count,
            "lateCount": late_count,
            "percentage": pct,
            "status": _status_label(pct) if held else "No Data",
        })

    # History directly from all attendance records
    history = []
    for r in all_records:
        if not r.session or not r.session.course:
            continue
        c = r.session.course
        history.append({
            "courseCode": c.code,
            "courseTitle": c.title,
            "courseName": c.title,
            "date": r.session.session_date.isoformat(),
            "status": r.status,
            "division": r.session.division,
            "markedBy": r.session.marked_by.user.full_name if (r.session.marked_by and r.session.marked_by.user) else "Faculty Instructor",
        })

    overall_pct = round((total_attended / total_held) * 100, 1) if total_held else 0.0

    return jsonify({
        "success": True,
        "data": {
            "rows": rows,
            "history": history,
            "lateAttendancePolicy": {
                "weight": late_weight,
                "description": f"Late attendance is weighted as {late_weight}x class credit."
            },
            "overall": {
                "percentage": overall_pct,
                "held": total_held,
                "totalConducted": total_held,
                "attended": total_attended,
                "presentCount": total_present,
                "absentCount": total_absent,
                "lateCount": total_late,
                "missed": total_held - total_attended,
                "eligible": overall_pct >= 75 if total_held > 0 else True,
                "hasRecords": total_held > 0,
            },
        },
    })


@bp.get("/roll-call")
@roles_required("faculty", "admin")
def get_roll_call():
    """Faculty or Admin classroom roster with marks filtered by course and division."""
    user = current_user()
    course_code = request.args.get("courseCode")
    if not course_code:
        raise ValidationError("courseCode is required.")

    raw_date = request.args.get("date")
    if raw_date:
        try:
            session_date = date.fromisoformat(str(raw_date)[:10])
        except (ValueError, TypeError):
            session_date = date.today()
    else:
        session_date = date.today()

    division = (request.args.get("division") or "A").strip().upper()

    course = Course.query.filter_by(code=course_code).first()
    if not course:
        return jsonify({"success": False, "error": "Course not found."}), 404

    matching_assignment = None
    # Server-side RBAC: Faculty must be assigned to this course and division
    if user.role == "faculty":
        fac = user.faculty_profile
        matching_assignment = next(
            (a for a in fac.assignments if a.course_id == course.id and (a.division.upper() == division or a.division.upper() == "ALL")),
            None
        )
        if not matching_assignment:
            return jsonify({
                "success": False,
                "error": f"You are not assigned to teach course {course.code} for Division {division}."
            }), 403

    session_row = AttendanceSession.query.options(
        db.selectinload(AttendanceSession.records)
    ).filter_by(
        course_id=course.id, session_date=session_date, division=division
    ).first()

    marks_by_student = {}
    if session_row:
        marks_by_student = {r.student_id: r.status for r in session_row.records}

    target_sem = matching_assignment.semester if matching_assignment else course.semester

    # Relational student query with eager-loaded user & department to eliminate N+1
    enrolled_students = (
        Student.query.options(
            db.joinedload(Student.user),
            db.joinedload(Student.department)
        )
        .join(Enrollment, Student.id == Enrollment.student_id)
        .filter(
            Enrollment.course_id == course.id,
            Student.department_id == course.department_id,
            Student.semester == target_sem,
            db.or_(Student.division == division, Student.division.is_(None))
        )
        .all()
    )

    if not enrolled_students:
        enrolled_students = (
            Student.query.options(
                db.joinedload(Student.user),
                db.joinedload(Student.department)
            )
            .join(Enrollment, Student.id == Enrollment.student_id)
            .filter(
                Enrollment.course_id == course.id,
                Student.department_id == course.department_id,
                db.or_(Student.division == division, Student.division.is_(None))
            )
            .all()
        )

    roster = []
    for s in enrolled_students:
        roster.append({
            "studentId": s.student_code,
            "prn": s.prn or s.student_code,
            "rollNumber": s.roll_number,
            "roll_number": s.roll_number,
            "name": s.user.full_name if s.user else None,
            "department": s.department.name if s.department else None,
            "semester": s.semester,
            "division": s.division or division,
            "status": marks_by_student.get(s.id, "present"),
        })

    roster.sort(key=lambda x: str(x.get("rollNumber") or x.get("prn") or x.get("studentId") or ""))

    return jsonify({
        "success": True,
        "data": {
            "courseCode": course.code,
            "courseTitle": course.title,
            "date": session_date.isoformat(),
            "division": division,
            "roster": roster,
        },
    })


@bp.post("/roll-call")
@bp.post("/sessions")
@roles_required("faculty", "admin")
def save_roll_call():
    """Faculty or Admin saves the day's roll-call/session in a batch transaction."""
    user = current_user()
    data = request.get_json(silent=True) or {}
    course_code = data.get("courseCode") or data.get("course_code")
    if not course_code or not data.get("records"):
        raise ValidationError("Course code and records list are required.")

    course = Course.query.filter_by(code=course_code).first()
    if not course:
        return jsonify({"success": False, "error": "Course not found."}), 404

    raw_date = data.get("date")
    if raw_date:
        try:
            session_date = date.fromisoformat(str(raw_date)[:10])
        except (ValueError, TypeError):
            session_date = date.today()
    else:
        session_date = date.today()
    division = (data.get("division") or "A").strip().upper()

    if user.role == "faculty":
        fac = user.faculty_profile
        is_assigned = any(
            a.course_id == course.id and (a.division.upper() == division or a.division.upper() == "ALL")
            for a in fac.assignments
        ) or (course.instructor_id == fac.id)
        if not is_assigned:
            return jsonify({
                "success": False,
                "error": "You can only mark attendance for your assigned courses and divisions."
            }), 403

    session_row = AttendanceSession.query.filter_by(
        course_id=course.id, session_date=session_date, division=division
    ).first()
    if not session_row:
        session_row = AttendanceSession(
            course_id=course.id,
            marked_by_id=user.faculty_profile.id if user.faculty_profile else None,
            division=division,
            session_date=session_date,
        )
        db.session.add(session_row)
        db.session.flush()

    # Pre-fetch all students matching the incoming IDs in a single query
    incoming_stu_ids = [str(rec.get("studentId") or rec.get("student_id")).strip() for rec in data["records"] if (rec.get("studentId") or rec.get("student_id"))]
    int_ids = [int(x) for x in incoming_stu_ids if x.isdigit()]

    student_filters = [
        Student.student_code.in_(incoming_stu_ids),
        Student.prn.in_(incoming_stu_ids)
    ]
    if int_ids:
        student_filters.append(Student.id.in_(int_ids))

    all_matched_students = Student.query.filter(db.or_(*student_filters)).all()
    student_lookup = {}
    for s in all_matched_students:
        student_lookup[s.student_code] = s
        if s.prn:
            student_lookup[s.prn] = s
        student_lookup[str(s.id)] = s

    student_db_ids = [s.id for s in all_matched_students]

    # Pre-fetch enrollments in a single query
    enrolled_set = set(
        e.student_id for e in Enrollment.query.filter(
            Enrollment.course_id == course.id,
            Enrollment.student_id.in_(student_db_ids)
        ).all()
    ) if student_db_ids else set()

    # Pre-fetch existing records for this session in a single query
    existing_records = {
        r.student_id: r for r in AttendanceRecord.query.filter_by(session_id=session_row.id).all()
    }

    for rec in data["records"]:
        stu_id = str(rec.get("studentId") or rec.get("student_id") or "").strip()
        status = (rec.get("status") or "").lower()
        if not stu_id or not status:
            raise ValidationError("Each record needs studentId/student_id and status.")
        if status not in ("present", "absent", "late"):
            raise ValidationError("status must be present, absent, or late.")

        student = student_lookup.get(stu_id)
        if not student:
            raise ValidationError(f"Unknown student: {stu_id}")

        if student.id not in enrolled_set:
            return jsonify({
                "success": False,
                "error": f"Student {stu_id} is not enrolled in {course.code}."
            }), 403

        if student.division and student.division.upper() != division and division != "ALL":
            return jsonify({
                "success": False,
                "error": f"Student {stu_id} does not belong to Division {division}."
            }), 403

        existing = existing_records.get(student.id)
        if existing:
            existing.status = status
        else:
            db.session.add(AttendanceRecord(
                session_id=session_row.id, student_id=student.id, status=status
            ))

    db.session.commit()
    return jsonify({"success": True})
