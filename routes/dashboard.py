from datetime import date, timedelta
from flask import Blueprint, jsonify
from models import (
    Student, Faculty, Course, Result, Notice, StudyMaterial,
    AttendanceRecord, AttendanceSession, Enrollment,
)
from utils.auth import login_required, current_user

bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")


@bp.get("/summary")
@login_required
def summary():
    user = current_user()

    if user.role == "student":
        student = user.student_profile
        records = AttendanceRecord.query.filter_by(student_id=student.id).all()
        held = len(records)
        attended = sum(1 for r in records if r.status in ("present", "late"))
        attendance_pct = round((attended / held) * 100, 1) if held else 0.0

        published = [r for r in student.results if r.is_published]
        cgpa = round(sum(r.total_marks for r in published) / (len(published) * 10), 2) if published else 0.0

        from extensions import db
        recent_notices = Notice.query.filter(
            Notice.created_at >= date.today() - timedelta(days=7),
            db.and_(
                db.or_(Notice.department_id.is_(None), Notice.department_id == student.department_id),
                db.or_(Notice.year_label.is_(None), Notice.year_label == student.year_label),
                db.or_(Notice.semester.is_(None), Notice.semester == student.semester),
                db.or_(Notice.division.is_(None), Notice.division.ilike("All"), Notice.division.ilike(student.division or "A")),
            )
        ).count()

        cohort_info = {
            "department": student.department.name if student.department else "General",
            "year": student.year_label,
            "semester": f"Sem {student.semester}",
            "division": f"Div {student.division or 'A'}",
            "studentCode": student.student_code,
            "prn": student.prn or student.student_code,
            "badge": f"{student.department.code if student.department else 'CSE'} • {student.year_label} • Sem {student.semester} • Div {student.division or 'A'}"
        }

        data = {
            "attendancePct": attendance_pct,
            "cgpa": cgpa,
            "enrolledCourses": len(student.enrollments) or Course.query.filter_by(department_id=student.department_id, semester=student.semester).count(),
            "pendingTasks": recent_notices,
            "cohort": cohort_info,
        }

    elif user.role == "faculty":
        faculty = user.faculty_profile
        from extensions import db
        assigned_ids = {a.course_id for a in faculty.assignments}
        instructed_ids = {c.id for c in Course.query.filter_by(instructor_id=faculty.id).all()}
        all_course_ids = list(assigned_ids | instructed_ids)

        assigned_divs = {a.division.upper() for a in faculty.assignments} or {"A"}

        total_students = (
            len({
                e.student_id for e in Enrollment.query.join(Student).filter(
                    Enrollment.course_id.in_(all_course_ids),
                    db.or_(Student.division.in_(assigned_divs), Student.division.is_(None))
                ).all()
            })
            if all_course_ids else 0
        )
        if total_students == 0 and all_course_ids:
            total_students = Student.query.filter(
                Student.department_id == faculty.department_id,
                Student.division.in_(assigned_divs)
            ).count()

        today_marked = {
            s.course_id for s in AttendanceSession.query.filter(
                AttendanceSession.course_id.in_(all_course_ids),
                AttendanceSession.session_date == date.today(),
            ).all()
        }
        attendance_pending = len([c for c in all_course_ids if c not in today_marked])
        uploaded_notes = StudyMaterial.query.filter_by(uploaded_by_id=user.id).count()

        data = {
            "todayClasses": len(all_course_ids),
            "totalStudents": total_students,
            "attendancePending": attendance_pending,
            "uploadedNotes": uploaded_notes,
            "assignedDivisions": list(assigned_divs),
        }

    else:  # admin
        data = {
            "totalStudents": Student.query.count(),
            "facultyMembers": Faculty.query.count(),
            "activeCourses": Course.query.filter_by(status="active").count(),
            "systemHealth": 100,
        }

    return jsonify({"success": True, "data": data})
