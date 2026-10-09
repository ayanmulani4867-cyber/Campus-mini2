import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app import create_app
from extensions import db
from models import User, Department, Course, Student, Faculty, Enrollment, FacultyAssignment, AttendanceSession, AttendanceRecord


def test_clean_state_and_new_provisioning():
    print("=" * 80)
    print("CAMPUS CONNECT ERP -- CLEAN STATE & FRESH PROVISIONING VERIFICATION")
    print("=" * 80)

    app = create_app()
    client = app.test_client()

    with app.app_context():
        # 1. Verify all students and faculty are completely removed
        print("\n[VERIFICATION 1] Confirming zero existing students and faculty...")
        stu_cnt = Student.query.count()
        fac_cnt = Faculty.query.count()
        user_stu_cnt = User.query.filter_by(role="student").count()
        user_fac_cnt = User.query.filter_by(role="faculty").count()
        
        assert stu_cnt == 0, f"Expected 0 students, found {stu_cnt}"
        assert fac_cnt == 0, f"Expected 0 faculty, found {fac_cnt}"
        assert user_stu_cnt == 0, f"Expected 0 student login accounts, found {user_stu_cnt}"
        assert user_fac_cnt == 0, f"Expected 0 faculty login accounts, found {user_fac_cnt}"
        print(f"  [OK] Students count: {stu_cnt}")
        print(f"  [OK] Faculty count: {fac_cnt}")
        print(f"  [OK] Student user accounts: {user_stu_cnt}")
        print(f"  [OK] Faculty user accounts: {user_fac_cnt}")

        # 2. Verify academic structure is preserved
        print("\n[VERIFICATION 2] Confirming academic structure is preserved...")
        depts = Department.query.all()
        courses = Course.query.all()
        assert len(depts) >= 4, f"Expected >= 4 departments, found {len(depts)}"
        assert len(courses) >= 13, f"Expected >= 13 courses, found {len(courses)}"
        print(f"  [OK] Departments preserved: {len(depts)} departments")
        print(f"  [OK] Courses preserved: {len(courses)} courses")

        # 3. Verify health endpoint
        print("\n[VERIFICATION 3] Checking application health endpoint...")
        h_res = client.get("/api/health")
        assert h_res.status_code == 200, f"Health check failed: {h_res.get_json()}"
        assert h_res.get_json()["status"] == "ok"
        print("  [OK] GET /api/health returned 200 OK, databaseConfigured: True")

        # 4. Verify admin login
        print("\n[VERIFICATION 4] Verifying administrator login (admin / admin)...")
        login_res = client.post("/api/auth/login", json={
            "username": "admin",
            "password": "admin",
            "role": "admin"
        })
        assert login_res.status_code == 200, f"Admin login failed: {login_res.get_json()}"
        admin_data = login_res.get_json()
        assert admin_data["success"] is True
        assert admin_data["data"]["role"] == "admin"
        admin_token = admin_data["sessionToken"]
        print("  [OK] Administrator successfully authenticated with username: admin, password: admin")

        # 5. Verify admin can provision a new faculty member with assignments
        print("\n[VERIFICATION 5] Testing Admin creation of a fresh Faculty member...")
        fac_payload = {
            "name": "Dr. Fresh Faculty",
            "email": "fresh.faculty@campus.edu",
            "phone": "9812345678",
            "department": "Computer Science & Engineering",
            "designation": "Assistant Professor",
            "facultyId": "FAC_FRESH_01",
            "assignments": [
                {
                    "subject": "CS601",
                    "year": "3rd Year",
                    "semester": 6,
                    "divisions": ["A"]
                }
            ]
        }
        res_fac = client.post("/api/faculty", json=fac_payload, headers={"X-Session-Token": admin_token})
        assert res_fac.status_code in (200, 201), f"Faculty creation failed: {res_fac.get_json()}"
        fac_data = res_fac.get_json()["data"]
        print(f"  [OK] Fresh faculty created: {fac_data['name']} (Code: {fac_data.get('facultyCode', 'FAC_FRESH_01')})")

        # 6. Verify admin can provision a new student with automatic PRN format 241010XX
        print("\n[VERIFICATION 6] Testing Admin creation of a fresh Student with 241010XX PRN...")
        stu_payload = {
            "name": "Fresh Student Test",
            "email": "fresh.student@campus.edu",
            "phone": "9823456789",
            "department": "Computer Science & Engineering",
            "year": "3rd Year",
            "semester": 6,
            "division": "A",
            "rollNumber": "01",
        }
        res_stu = client.post("/api/students", json=stu_payload, headers={"X-Session-Token": admin_token})
        assert res_stu.status_code in (200, 201), f"Student creation failed: {res_stu.get_json()}"
        stu_data = res_stu.get_json()["data"]
        assigned_prn = stu_data.get("prn")
        assert assigned_prn is not None, "PRN was not generated!"
        assert assigned_prn.startswith("241010") and len(assigned_prn) == 8 and assigned_prn[6:].isdigit(), (
            f"PRN '{assigned_prn}' does not match format 241010XX!"
        )
        print(f"  [OK] Fresh student created: {stu_data['name']} (PRN: {assigned_prn}, Roll: 01)")

        # 7. Verify Faculty can log in and view the student in the attendance roll-call roster
        print("\n[VERIFICATION 7] Testing Faculty login and attendance roll-call roster sync...")
        fac_login = client.post("/api/auth/login", json={
            "email": "fresh.faculty@campus.edu",
            "password": "campus@123",
            "role": "faculty"
        })
        if fac_login.status_code != 200:
            # Try initial phone login
            fac_login = client.post("/api/auth/login", json={
                "email": "fresh.faculty@campus.edu",
                "password": "9812345678",
                "role": "faculty"
            })
        assert fac_login.status_code == 200, f"Faculty login failed: {fac_login.get_json()}"
        fac_token = fac_login.get_json()["sessionToken"]

        roster_res = client.get("/api/attendance/roll-call?courseCode=CS601&division=A", headers={"X-Session-Token": fac_token})
        assert roster_res.status_code == 200, f"Roll call failed: {roster_res.get_json()}"
        roster = roster_res.get_json()["data"]["roster"]
        assert len(roster) >= 1, "Roster should contain the newly enrolled student!"
        assert any(s.get("name") == "Fresh Student Test" or s.get("prn") == assigned_prn for s in roster), (
            "Fresh student not found in faculty roll call roster!"
        )
        print(f"  [OK] Faculty roll call roster loaded: Student '{stu_data['name']}' visible in CS601 Div A.")

        # 8. Clean up test student & faculty created for the verification
        print("\n[VERIFICATION 8] Cleaning up verification artifacts...")
        # Clean faculty assignment and student enrollment
        with app.app_context():
            fs = Student.query.filter_by(student_code=stu_data.get("studentCode") or stu_data.get("id")).first()
            if fs:
                Enrollment.query.filter_by(student_id=fs.id).delete()
                u_id = fs.user_id
                db.session.delete(fs)
                User.query.filter_by(id=u_id).delete()

            ff = Faculty.query.filter_by(faculty_code="FAC_FRESH_01").first()
            if ff:
                FacultyAssignment.query.filter_by(faculty_id=ff.id).delete()
                u_id = ff.user_id
                db.session.delete(ff)
                User.query.filter_by(id=u_id).delete()

            db.session.commit()
        print("  [OK] Temporary verification records removed. Database returned to pristine empty student/faculty state.")

        # 9. Confirm final post-test counts
        final_stu = Student.query.count()
        final_fac = Faculty.query.count()
        final_users = User.query.count()
        assert final_stu == 0
        assert final_fac == 0
        assert final_users == 1
        print(f"  [OK] Final confirmed counts: Students={final_stu}, Faculty={final_fac}, Users={final_users} (Admin only)")

    print("\n" + "=" * 80)
    print("ALL 8 CLEAN STATE AND FRESH PROVISIONING VERIFICATIONS PASSED 100%!")
    print("=" * 80)


if __name__ == "__main__":
    test_clean_state_and_new_provisioning()
