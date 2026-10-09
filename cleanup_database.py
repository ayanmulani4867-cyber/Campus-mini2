import sys
from pathlib import Path
from sqlalchemy import text

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app import create_app
from extensions import db
from models import (
    User, Department, Course, Enrollment, Student, Faculty, FacultyAssignment,
    AttendanceSession, AttendanceRecord, Result, Notice, StudyMaterial, Event,
    LeaveRequest, Assignment, AssignmentSubmission
)
from seed import ensure_default_admin


def perform_database_cleanup(dry_run=False):
    app = create_app()
    with app.app_context():
        engine = db.engine
        db_url = str(engine.url)
        print("=" * 80)
        print("CAMPUS CONNECT ERP -- DATABASE CLEANUP: REMOVE STUDENTS & FACULTY")
        print("=" * 80)
        print(f"Target Database URL: {db_url}")
        if "campus_connect" not in db_url:
            raise RuntimeError(f"Safety check failed: Target database {db_url} is not 'campus_connect'!")
        print("Safety check passed: Verified target database is 'campus_connect'.")

        # Ensure default admin exists first
        admin = ensure_default_admin()
        print(f"Admin verified: ID={admin.id}, Email={admin.email}, Role={admin.role}")

        # Pre-cleanup record counts
        pre_counts = {
            "users_total": User.query.count(),
            "users_admin": User.query.filter_by(role="admin").count(),
            "users_faculty": User.query.filter_by(role="faculty").count(),
            "users_student": User.query.filter_by(role="student").count(),
            "students": Student.query.count(),
            "faculty": Faculty.query.count(),
            "departments": Department.query.count(),
            "courses": Course.query.count(),
            "faculty_assignments": FacultyAssignment.query.count(),
            "enrollments": Enrollment.query.count(),
            "attendance_sessions": AttendanceSession.query.count(),
            "attendance_records": AttendanceRecord.query.count(),
            "results": Result.query.count(),
            "assignments": Assignment.query.count(),
            "assignment_submissions": AssignmentSubmission.query.count(),
            "study_materials": StudyMaterial.query.count(),
            "leave_requests": LeaveRequest.query.count(),
            "notices": Notice.query.count(),
            "events": Event.query.count(),
        }

        print("\n--- PRE-CLEANUP RECORD COUNTS ---")
        for k, v in pre_counts.items():
            print(f"  * {k:25s}: {v}")

        print("\nExecuting transactional removal in strict foreign-key order...")

        try:
            # 1. Clear course instructor links
            r_c = db.session.execute(text("UPDATE courses SET instructor_id = NULL;"))
            print(f"  [1] Cleared instructor_id on courses: {r_c.rowcount} rows updated")

            # 2. Reassign study materials to admin so course notes library is preserved
            r_sm = db.session.execute(
                text("UPDATE study_materials SET uploaded_by_id = :aid;"),
                {"aid": admin.id}
            )
            print(f"  [2] Reassigned study materials uploaded_by_id to admin: {r_sm.rowcount} rows updated")

            # 3. Delete student & faculty dependent records in topological FK order
            r_as = db.session.execute(text("DELETE FROM assignment_submissions;"))
            print(f"  [3] Deleted assignment submissions: {r_as.rowcount} rows deleted")

            r_a = db.session.execute(text("DELETE FROM assignments;"))
            print(f"  [4] Deleted assignments: {r_a.rowcount} rows deleted")

            r_ar = db.session.execute(text("DELETE FROM attendance_records;"))
            print(f"  [5] Deleted attendance records: {r_ar.rowcount} rows deleted")

            r_sess = db.session.execute(text("DELETE FROM attendance_sessions;"))
            print(f"  [6] Deleted attendance sessions: {r_sess.rowcount} rows deleted")

            r_res = db.session.execute(text("DELETE FROM results;"))
            print(f"  [7] Deleted results: {r_res.rowcount} rows deleted")

            r_lr = db.session.execute(text("DELETE FROM leave_requests;"))
            print(f"  [8] Deleted leave requests: {r_lr.rowcount} rows deleted")

            r_enr = db.session.execute(text("DELETE FROM enrollments;"))
            print(f"  [9] Deleted enrollments: {r_enr.rowcount} rows deleted")

            r_fa = db.session.execute(text("DELETE FROM faculty_assignments;"))
            print(f"  [10] Deleted faculty assignments: {r_fa.rowcount} rows deleted")

            # 4. Delete Students & Faculty profile tables
            r_stu = db.session.execute(text("DELETE FROM students;"))
            print(f"  [11] Deleted student records: {r_stu.rowcount} rows deleted")

            r_fac = db.session.execute(text("DELETE FROM faculty;"))
            print(f"  [12] Deleted faculty records: {r_fac.rowcount} rows deleted")

            # 5. Delete UserSessions for student and faculty users
            r_sess_u = db.session.execute(text(
                "DELETE FROM user_sessions WHERE user_id IN (SELECT id FROM users WHERE role IN ('student', 'faculty'));"
            ))
            print(f"  [13] Deleted user sessions for students & faculty: {r_sess_u.rowcount} rows deleted")

            # 6. Delete User accounts for students and faculty
            r_u = db.session.execute(text("DELETE FROM users WHERE role IN ('student', 'faculty');"))
            print(f"  [14] Deleted student & faculty user accounts: {r_u.rowcount} rows deleted")

            if dry_run:
                db.session.rollback()
                print("\n[DRY RUN] Transaction rolled back. No permanent changes made.")
                return

            db.session.commit()
            print("\n[SUCCESS] Transaction committed successfully.")

        except Exception as e:
            db.session.rollback()
            print("\n[ERROR] Cleanup failed. Transaction rolled back:", e)
            raise

        # Post-cleanup record verification
        post_counts = {
            "users_total": User.query.count(),
            "users_admin": User.query.filter_by(role="admin").count(),
            "users_faculty": User.query.filter_by(role="faculty").count(),
            "users_student": User.query.filter_by(role="student").count(),
            "students": Student.query.count(),
            "faculty": Faculty.query.count(),
            "departments": Department.query.count(),
            "courses": Course.query.count(),
            "faculty_assignments": FacultyAssignment.query.count(),
            "enrollments": Enrollment.query.count(),
            "attendance_sessions": AttendanceSession.query.count(),
            "attendance_records": AttendanceRecord.query.count(),
            "results": Result.query.count(),
            "assignments": Assignment.query.count(),
            "assignment_submissions": AssignmentSubmission.query.count(),
            "study_materials": StudyMaterial.query.count(),
            "leave_requests": LeaveRequest.query.count(),
            "notices": Notice.query.count(),
            "events": Event.query.count(),
        }

        print("\n--- POST-CLEANUP RECORD COUNTS ---")
        for k, v in post_counts.items():
            print(f"  * {k:25s}: {v}")

        # Assertions
        assert post_counts["students"] == 0, "Expected 0 students remaining!"
        assert post_counts["faculty"] == 0, "Expected 0 faculty remaining!"
        assert post_counts["users_student"] == 0, "Expected 0 student user accounts remaining!"
        assert post_counts["users_faculty"] == 0, "Expected 0 faculty user accounts remaining!"
        assert post_counts["users_admin"] == 1, "Admin account must be preserved!"
        assert post_counts["departments"] >= 4, "Departments must remain intact!"
        assert post_counts["courses"] >= 13, "Courses must remain intact!"
        assert post_counts["faculty_assignments"] == 0, "Faculty assignments must be cleared!"
        assert post_counts["enrollments"] == 0, "Enrollments must be cleared!"
        assert post_counts["attendance_records"] == 0, "Attendance records must be cleared!"
        assert post_counts["results"] == 0, "Results must be cleared!"

        print("\n" + "=" * 80)
        print("DATABASE CLEANUP VERIFIED: ALL STUDENTS AND FACULTY COMPLETELY REMOVED!")
        print("=" * 80)


if __name__ == "__main__":
    is_dry = "--dry-run" in sys.argv
    perform_database_cleanup(dry_run=is_dry)
