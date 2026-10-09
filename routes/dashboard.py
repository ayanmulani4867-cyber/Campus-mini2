from datetime import date, timedelta
from flask import Blueprint, jsonify
from models import (
    Student, Faculty, Course, Result, Notice, StudyMaterial,
    AttendanceRecord, AttendanceSession, Enrollment,
)
from utils.auth import login_required, current_user

bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")


@bp.get("/summary")
@bp.get("/stats")
@login_required
def summary():
    user = current_user()

    if user.role == "student":
        student = user.student_profile
        from extensions import db
        # SQL aggregation for attendance
        att_stats = db.session.query(
            db.func.count(AttendanceRecord.id),
            db.func.count(db.case((AttendanceRecord.status.in_(("present", "late")), 1)))
        ).filter(AttendanceRecord.student_id == student.id).first()
        held = att_stats[0] or 0
        attended = att_stats[1] or 0
        attendance_pct = round((attended / held) * 100, 1) if held else 0.0

        # SQL aggregation for published results CGPA
        res_stats = db.session.query(
            db.func.count(Result.id),
            db.func.sum(Result.internal_marks + Result.end_sem_marks)
        ).filter(Result.student_id == student.id, Result.is_published.is_(True)).first()
        res_cnt = res_stats[0] or 0
        res_sum = float(res_stats[1] or 0.0)
        cgpa = round(res_sum / (res_cnt * 10), 2) if res_cnt else 0.0

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

        enrolled_count = db.session.query(db.func.count(Enrollment.id)).filter_by(student_id=student.id).scalar()
        if not enrolled_count:
            enrolled_count = Course.query.filter_by(department_id=student.department_id, semester=student.semester).count()

        data = {
            "attendancePct": attendance_pct,
            "cgpa": cgpa,
            "enrolledCourses": enrolled_count,
            "pendingTasks": recent_notices,
            "cohort": cohort_info,
        }

    elif user.role == "faculty":
        faculty = user.faculty_profile
        from extensions import db
        assigned_ids = {a.course_id for a in faculty.assignments}
        instructed_ids = {c[0] for c in Course.query.with_entities(Course.id).filter_by(instructor_id=faculty.id).all()}
        all_course_ids = list(assigned_ids | instructed_ids)

        assigned_divs = {a.division.upper() for a in faculty.assignments} or {"A"}

        if all_course_ids:
            total_students = db.session.query(
                db.func.count(db.distinct(Enrollment.student_id))
            ).join(Student, Student.id == Enrollment.student_id).filter(
                Enrollment.course_id.in_(all_course_ids),
                db.or_(Student.division.in_(assigned_divs), Student.division.is_(None))
            ).scalar() or 0
        else:
            total_students = 0

        if total_students == 0 and all_course_ids:
            total_students = Student.query.filter(
                Student.department_id == faculty.department_id,
                Student.division.in_(assigned_divs)
            ).count()

        today_marked = {
            s[0] for s in db.session.query(AttendanceSession.course_id).filter(
                AttendanceSession.course_id.in_(all_course_ids),
                AttendanceSession.session_date == date.today(),
            ).all()
        } if all_course_ids else set()

        attendance_pending = len([c for c in all_course_ids if c not in today_marked])
        uploaded_notes = StudyMaterial.query.filter_by(uploaded_by_id=user.id).count()

        data = {
            "todayClasses": len(all_course_ids),
            "totalStudents": total_students,
            "total_students": total_students,
            "attendancePending": attendance_pending,
            "uploadedNotes": uploaded_notes,
            "assignedDivisions": list(assigned_divs),
        }

    else:  # admin
        from extensions import db
        stu_cnt = Student.query.count()
        fac_cnt = Faculty.query.count()
        crs_stats = db.session.query(
            db.func.count(Course.id),
            db.func.count(db.case((Course.status.ilike("active"), 1))),
            db.func.count(db.case((Course.status.ilike("inactive"), 1))),
            db.func.count(db.distinct(Course.department_id))
        ).first()

        data = {
            "totalStudents": stu_cnt,
            "total_students": stu_cnt,
            "facultyMembers": fac_cnt,
            "totalFaculty": fac_cnt,
            "total_faculty": fac_cnt,
            "activeCourses": crs_stats[1] or 0,
            "inactiveCourses": crs_stats[2] or 0,
            "totalCourses": crs_stats[0] or 0,
            "total_courses": crs_stats[0] or 0,
            "departmentsWithCourses": crs_stats[3] or 0,
            "systemHealth": 100,
        }

    return jsonify({"success": True, "data": data})
