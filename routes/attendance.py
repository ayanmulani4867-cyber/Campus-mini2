from datetime import date
from flask import Blueprint, request, jsonify
from extensions import db
from models import (
    Student, Course, AttendanceSession, AttendanceRecord, Enrollment,
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
    """Subject-wise Held/Attended/Percentage table.
    Students see their own; faculty/admin can pass ?studentId=STU..."""
    user = current_user()
    if user.role == "student":
        student = user.student_profile
    else:
        code = request.args.get("studentId")
        if not code:
            raise ValidationError("studentId is required for faculty/admin lookups.")
        student = Student.query.filter_by(student_code=code).first()
        if not student:
            return jsonify({"success": False, "error": "Student not found."}), 404

    rows = []
    total_held = total_attended = 0
    for enr in student.enrollments:
        course = enr.course
        records = (
            AttendanceRecord.query.join(AttendanceSession)
            .filter(AttendanceSession.course_id == course.id, AttendanceRecord.student_id == student.id)
            .all()
        )
        held = len(records)
        attended = sum(1 for r in records if r.status in ("present", "late"))
        pct = round((attended / held) * 100, 1) if held else 0.0
        total_held += held
        total_attended += attended
        rows.append({
            "courseCode": course.code,
            "courseTitle": course.title,
            "instructor": course.instructor.user.full_name if course.instructor else None,
            "held": held,
            "attended": attended,
            "percentage": pct,
            "status": _status_label(pct) if held else "No Data",
        })

    overall_pct = round((total_attended / total_held) * 100, 1) if total_held else 0.0
    return jsonify({
        "success": True,
        "data": {
            "rows": rows,
            "overall": {
                "percentage": overall_pct,
                "held": total_held,
                "attended": total_attended,
                "missed": total_held - total_attended,
                "eligible": overall_pct >= 75,
            },
        },
    })


@bp.get("/roll-call")
@roles_required("faculty")
def get_roll_call():
    """Faculty's classroom roster with today's marks filtered by course and division."""
    course_code = request.args.get("courseCode")
    if not course_code:
        raise ValidationError("courseCode is required.")
    session_date = request.args.get("date", date.today().isoformat())
    division = (request.args.get("division") or "A").strip().upper()

    course = Course.query.filter_by(code=course_code).first()
    if not course:
        return jsonify({"success": False, "error": "Course not found."}), 404

    session_row = AttendanceSession.query.filter_by(
        course_id=course.id, session_date=session_date, division=division
    ).first()
    marks_by_student = {}
    if session_row:
        marks_by_student = {r.student_id: r.status for r in session_row.records}

    # Find enrolled students belonging to this course & division
    enrolled_students = (
        Student.query.join(Enrollment)
        .filter(Enrollment.course_id == course.id, db.or_(Student.division == division, Student.division.is_(None)))
        .all()
    )

    # Fallback to cohort students if enrollment records were not explicitly created
    if not enrolled_students:
        from models import FacultyAssignment
        assigned_sems = [a.semester for a in course.faculty_assignments if a.division in (division, "ALL")]
        target_sems = set([course.semester] + [s for s in assigned_sems if s])
        enrolled_students = Student.query.filter(
            Student.department_id == course.department_id,
            Student.semester.in_(target_sems),
            db.or_(Student.division == division, Student.division.is_(None))
        ).all()

    roster = []
    for s in enrolled_students:
        roster.append({
            "studentId": s.student_code,
            "prn": s.prn or s.student_code,
            "name": s.user.full_name,
            "department": s.department.name if s.department else None,
            "semester": s.semester,
            "division": s.division or division,
            "status": marks_by_student.get(s.id, "present"),
        })

    # Sort roster by PRN or name
    roster.sort(key=lambda x: str(x.get("prn") or x.get("name") or ""))

    return jsonify({
        "success": True,
        "data": {
            "courseCode": course.code,
            "courseTitle": course.title,
            "date": session_date,
            "division": division,
            "roster": roster,
        },
    })


@bp.post("/roll-call")
@bp.post("/sessions")
@roles_required("faculty", "admin")
def save_roll_call():
    """Faculty or Admin saves the day's roll-call/session: {courseCode, date, division, records: [{studentId, status}]}"""
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
        is_assigned = (course.instructor_id == fac.id) or any(
            a.course_id == course.id and a.division.upper() == division for a in fac.assignments
        ) or any(a.course_id == course.id for a in fac.assignments)
        if not is_assigned:
            return jsonify({"success": False, "error": "You can only mark attendance for your assigned courses and classes."}), 403

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

    for rec in data["records"]:
        stu_id = rec.get("studentId") or rec.get("student_id")
        status = (rec.get("status") or "").lower()
        if not stu_id or not status:
            raise ValidationError("Each record needs studentId/student_id and status.")
        if status not in ("present", "absent", "late"):
            raise ValidationError("status must be present, absent, or late.")
        student = Student.query.filter(
            db.or_(
                Student.student_code == stu_id,
                Student.prn == stu_id,
                Student.id == int(stu_id) if str(stu_id).isdigit() else False
            )
        ).first()
        if not student:
            raise ValidationError(f"Unknown student: {stu_id}")

        existing = AttendanceRecord.query.filter_by(
            session_id=session_row.id, student_id=student.id
        ).first()
        if existing:
            existing.status = status
        else:
            db.session.add(AttendanceRecord(
                session_id=session_row.id, student_id=student.id, status=status
            ))

    db.session.commit()
    return jsonify({"success": True})
