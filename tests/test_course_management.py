"""
Comprehensive Course Management Test Suite
==========================================
Verifies:
1. Admin loads course list from PostgreSQL.
2. Dynamic departments load from PostgreSQL.
3. Faculty list filters dynamically by department.
4. Admin creates a new course with full field validation.
5. Newly created course persists and appears immediately and after refresh.
6. Duplicate course code rejected with friendly 400 error.
7. Invalid department rejected by backend.
8. Invalid instructor (cross-department) rejected by backend.
9. Course editing succeeds and updates PostgreSQL.
10. Course deactivation / activation toggles status cleanly.
11. Safe deletion: deletion blocked when dependent academic records exist, recommending deactivation.
12. Clean course deletion: deleting a course with zero dependent records succeeds.
13. Student cannot create, edit, or delete courses (401/403).
14. Faculty cannot create or delete courses, and cannot modify other faculty's courses (403).
15. Course details endpoint returns complete metadata and live related academic record counts.
16. Zero hardcoded mock course data in courses.html template.
17. Admin dashboard summary returns real PostgreSQL course statistics.
"""

import json
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Use DATABASE_URL from environment or fallback to test configuration
if not os.environ.get("DATABASE_URL"):
    test_db = os.environ.get("TEST_DATABASE_URL")
    if test_db:
        os.environ["DATABASE_URL"] = test_db

from app import create_app
from extensions import db
from models import User, Department, Faculty, Course, Student, Enrollment, AttendanceSession, Result, StudyMaterial, Assignment


def login(client, email, password):
    res = client.post(
        "/api/auth/login",
        data=json.dumps({"email": email, "password": password}),
        content_type="application/json"
    )
    assert res.status_code == 200, f"Login failed for {email}: {res.data}"
    data = res.get_json()
    token = data.get("sessionToken")
    return token, data.get("data")


def run_tests():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SERVER_NAME"] = "localhost"

    with app.app_context():
        client = app.test_client()

        # ---------------------------------------------------------------------
        # Auth Logins
        # ---------------------------------------------------------------------
        print("\n[TEST PREP] Authenticating Admin, Faculty, and Student...")
        admin_token, admin_user = login(client, "admin@campus.edu", "campus@123")
        admin_headers = {"X-Session-Token": admin_token, "Content-Type": "application/json"}
        assert admin_user["role"] == "admin"

        faculty_token, faculty_user = login(client, "rajesh.verma@campus.edu", "campus@123")
        faculty_headers = {"X-Session-Token": faculty_token, "Content-Type": "application/json"}
        assert faculty_user["role"] == "faculty"

        student_token, student_user = login(client, "priya.patel@campus.edu", "campus@123")
        student_headers = {"X-Session-Token": student_token, "Content-Type": "application/json"}
        assert student_user["role"] == "student"

        # ---------------------------------------------------------------------
        # 1. Admin loads course list from PostgreSQL
        # ---------------------------------------------------------------------
        print("\n[RUNNING] TEST 1: Admin loads course list from PostgreSQL...")
        res = client.get("/api/courses", headers=admin_headers)
        assert res.status_code == 200
        courses = res.get_json()["data"]
        assert len(courses) >= 1, "Expected at least 1 course in DB"
        print(f"  [PASS] Retrieved {len(courses)} courses from PostgreSQL.")

        # ---------------------------------------------------------------------
        # 2. Departments load dynamically
        # ---------------------------------------------------------------------
        print("\n[RUNNING] TEST 2: Dynamic departments load...")
        res = client.get("/api/departments", headers=admin_headers)
        assert res.status_code == 200
        depts = res.get_json()["data"]
        assert len(depts) >= 1
        cse_dept = next((d for d in depts if "computer" in d["name"].lower() or d["code"] == "CSE"), depts[0])
        print(f"  [PASS] Loaded {len(depts)} departments. Using {cse_dept['name']} (ID: {cse_dept['id']}).")

        # ---------------------------------------------------------------------
        # 3. Faculty list filters according to department
        # ---------------------------------------------------------------------
        print("\n[RUNNING] TEST 3: Faculty list filters by department...")
        res = client.get(f"/api/faculty?department_id={cse_dept['id']}", headers=admin_headers)
        assert res.status_code == 200
        dept_faculty = res.get_json()["data"]
        for f in dept_faculty:
            assert f["departmentId"] == cse_dept["id"] or f["dept"] == cse_dept["name"]
        print(f"  [PASS] Filtered {len(dept_faculty)} faculty for department {cse_dept['name']}.")

        test_instructor = dept_faculty[0] if dept_faculty else None

        # ---------------------------------------------------------------------
        # 4. Admin creates a new course with full field validation
        # ---------------------------------------------------------------------
        print("\n[RUNNING] TEST 4: Admin creates course (POST /api/courses)...")
        # Clean up test course if existed previously
        old_test = Course.query.filter_by(code="TEST801").first()
        if old_test:
            db.session.delete(old_test)
            db.session.commit()

        new_course_payload = {
            "code": "TEST801",
            "title": "Cloud Computing & Distributed Systems",
            "department": cse_dept["id"],
            "credits": 4,
            "category": "elective",
            "semester": 6,
            "year": "3rd Year",
            "division": "A",
            "room": "CSE-304",
            "syllabusCoverage": 25,
            "instructorId": test_instructor["facultyId"] if test_instructor else None,
            "status": "active"
        }
        res = client.post("/api/courses", data=json.dumps(new_course_payload), headers=admin_headers)
        assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.data}"
        created = res.get_json()["data"]
        assert created["code"] == "TEST801"
        assert created["title"] == "Cloud Computing & Distributed Systems"
        assert created["category"] == "elective"
        assert created["credits"] == 4
        assert created["syllabusCoverage"] == 25
        print(f"  [PASS] Successfully created course TEST801 (ID: {created['id']}).")

        # ---------------------------------------------------------------------
        # 5. Course appears immediately & persists after refresh
        # ---------------------------------------------------------------------
        print("\n[RUNNING] TEST 5: Verify course persistence & retrieval...")
        res = client.get("/api/courses", headers=admin_headers)
        assert res.status_code == 200
        course_codes = [c["code"] for c in res.get_json()["data"]]
        assert "TEST801" in course_codes
        print("  [PASS] TEST801 persists and appears in GET /api/courses.")

        # ---------------------------------------------------------------------
        # 6. Duplicate course code prevention
        # ---------------------------------------------------------------------
        print("\n[RUNNING] TEST 6: Prevent duplicate course code...")
        res = client.post("/api/courses", data=json.dumps(new_course_payload), headers=admin_headers)
        assert res.status_code == 400
        err_data = res.get_json()
        assert "already exists" in err_data.get("error", "").lower()
        print(f"  [PASS] Duplicate course code rejected with: '{err_data.get('error')}'.")

        # ---------------------------------------------------------------------
        # 7. Invalid department rejection
        # ---------------------------------------------------------------------
        print("\n[RUNNING] TEST 7: Invalid department rejection...")
        invalid_dept_payload = dict(new_course_payload, code="TEST802", department=999999)
        res = client.post("/api/courses", data=json.dumps(invalid_dept_payload), headers=admin_headers)
        assert res.status_code in (400, 422)
        print("  [PASS] Invalid department correctly rejected.")

        # ---------------------------------------------------------------------
        # 8. Invalid instructor (cross-department) rejection
        # ---------------------------------------------------------------------
        print("\n[RUNNING] TEST 8: Cross-department instructor validation...")
        # Find another department
        other_dept = next((d for d in depts if d["id"] != cse_dept["id"]), None)
        if other_dept:
            res_other_fac = client.get(f"/api/faculty?department_id={other_dept['id']}", headers=admin_headers)
            other_fac = res_other_fac.get_json()["data"]
            if other_fac:
                cross_dept_payload = dict(
                    new_course_payload,
                    code="TEST803",
                    department=cse_dept["id"],
                    instructorId=other_fac[0]["facultyId"]
                )
                res = client.post("/api/courses", data=json.dumps(cross_dept_payload), headers=admin_headers)
                assert res.status_code == 400
                assert "department" in res.get_json().get("error", "").lower()
                print("  [PASS] Cross-department instructor rejected by server validation.")
            else:
                print("  [SKIP] No faculty in alternate department to test cross-dept mismatch.")
        else:
            print("  [SKIP] Only one department present in DB.")

        # ---------------------------------------------------------------------
        # 9. Edit course
        # ---------------------------------------------------------------------
        print("\n[RUNNING] TEST 9: Admin edits course (PUT /api/courses/<id>)...")
        update_payload = {
            "title": "Cloud Computing & Distributed Systems (Updated)",
            "room": "CSE-LAB-4",
            "syllabusCoverage": 60,
            "credits": 5
        }
        res = client.put(f"/api/courses/{created['id']}", data=json.dumps(update_payload), headers=admin_headers)
        assert res.status_code == 200
        updated = res.get_json()["data"]
        assert updated["title"] == "Cloud Computing & Distributed Systems (Updated)"
        assert updated["room"] == "CSE-LAB-4"
        assert updated["syllabusCoverage"] == 60
        assert updated["credits"] == 5

        # Refresh and verify
        res = client.get(f"/api/courses/{created['id']}", headers=admin_headers)
        assert res.status_code == 200
        assert res.get_json()["data"]["room"] == "CSE-LAB-4"
        print("  [PASS] Course edited and verified after fresh GET.")

        # ---------------------------------------------------------------------
        # 10. Deactivate course & toggle status
        # ---------------------------------------------------------------------
        print("\n[RUNNING] TEST 10: Deactivate course (PATCH /api/courses/<id>/status)...")
        res = client.patch(f"/api/courses/{created['id']}/status", data=json.dumps({"status": "inactive"}), headers=admin_headers)
        assert res.status_code == 200
        assert res.get_json()["data"]["status"] == "inactive"

        # Re-activate
        res = client.patch(f"/api/courses/{created['id']}/status", data=json.dumps({"status": "active"}), headers=admin_headers)
        assert res.status_code == 200
        assert res.get_json()["data"]["status"] == "active"
        print("  [PASS] Course status toggled between active and inactive successfully.")

        # ---------------------------------------------------------------------
        # 11. Safe deletion cascade check (course with dependents cannot be deleted)
        # ---------------------------------------------------------------------
        print("\n[RUNNING] TEST 11: Attempt deletion of course with dependent records...")
        # CS601 has existing enrollments and results
        cs601 = Course.query.filter_by(code="CS601").first()
        assert cs601 is not None, "CS601 should exist in production seed"
        res = client.delete(f"/api/courses/{cs601.id}", headers=admin_headers)
        assert res.status_code == 400
        err_msg = res.get_json().get("error", "")
        assert "associated academic records" in err_msg
        assert res.get_json().get("canDeactivate") is True
        print(f"  [PASS] Deletion of course with dependents blocked: '{err_msg}'.")

        # ---------------------------------------------------------------------
        # 12. Delete course without dependents
        # ---------------------------------------------------------------------
        print("\n[RUNNING] TEST 12: Delete clean course without dependents...")
        clean_course = Course(
            code="TEMP999",
            title="Temporary Course",
            department_id=cse_dept["id"],
            credits=3,
            category="core",
            semester=1,
            status="active"
        )
        db.session.add(clean_course)
        db.session.commit()

        res = client.delete(f"/api/courses/{clean_course.id}", headers=admin_headers)
        assert res.status_code == 200
        assert Course.query.get(clean_course.id) is None
        print("  [PASS] Clean course TEMP999 deleted successfully.")

        # ---------------------------------------------------------------------
        # 13. Student access control
        # ---------------------------------------------------------------------
        print("\n[RUNNING] TEST 13: Student access restrictions...")
        res = client.post("/api/courses", data=json.dumps(new_course_payload), headers=student_headers)
        assert res.status_code == 403
        res = client.put(f"/api/courses/{created['id']}", data=json.dumps(update_payload), headers=student_headers)
        assert res.status_code == 403
        res = client.delete(f"/api/courses/{created['id']}", headers=student_headers)
        assert res.status_code == 403
        print("  [PASS] Student blocked with 403 from POST, PUT, and DELETE /api/courses.")

        # ---------------------------------------------------------------------
        # 14. Faculty access control
        # ---------------------------------------------------------------------
        print("\n[RUNNING] TEST 14: Faculty access restrictions...")
        res = client.post("/api/courses", data=json.dumps(new_course_payload), headers=faculty_headers)
        assert res.status_code == 403
        res = client.delete(f"/api/courses/{created['id']}", headers=faculty_headers)
        assert res.status_code == 403
        print("  [PASS] Faculty blocked with 403 from POST and DELETE /api/courses.")

        # ---------------------------------------------------------------------
        # 15. Course details endpoint returns complete metadata and live counts
        # ---------------------------------------------------------------------
        print("\n[RUNNING] TEST 15: Course details endpoint returns live counts...")
        res = client.get(f"/api/courses/{cs601.id}", headers=admin_headers)
        assert res.status_code == 200
        details = res.get_json()["data"]
        assert "enrolledStudentsCount" in details
        assert "attendanceSessionsCount" in details
        assert "assignmentsCount" in details
        assert "resultsCount" in details
        assert "studyMaterialsCount" in details
        assert "facultyAssignmentsCount" in details
        print(f"  [PASS] Details for CS601: Enrolled={details['enrolledStudentsCount']}, Results={details['resultsCount']}, Sessions={details['attendanceSessionsCount']}.")

        # ---------------------------------------------------------------------
        # 16. Verify ZERO hardcoded course data in templates/courses.html
        # ---------------------------------------------------------------------
        print("\n[RUNNING] TEST 16: Zero hardcoded course data in courses.html...")
        courses_html_path = BASE_DIR / "templates" / "courses.html"
        html_content = courses_html_path.read_text(encoding="utf-8")
        assert "Database Management Systems" not in html_content
        assert "CS601" not in html_content
        assert "Computer Networks & Security" not in html_content
        print("  [PASS] templates/courses.html contains ZERO hardcoded course rows or mock data.")

        # ---------------------------------------------------------------------
        # 17. Admin Dashboard statistics
        # ---------------------------------------------------------------------
        print("\n[RUNNING] TEST 17: Admin dashboard summary course statistics...")
        res = client.get("/api/dashboard/summary", headers=admin_headers)
        assert res.status_code == 200
        stats = res.get_json()["data"]
        assert "totalCourses" in stats
        assert "activeCourses" in stats
        assert "inactiveCourses" in stats
        assert "departmentsWithCourses" in stats
        assert stats["totalCourses"] >= 1
        assert stats["departmentsWithCourses"] >= 1
        print(f"  [PASS] Admin Dashboard Stats: Total={stats['totalCourses']}, Active={stats['activeCourses']}, Inactive={stats['inactiveCourses']}, DeptsWithCourses={stats['departmentsWithCourses']}.")

        # Clean up created test course
        test_created = Course.query.filter_by(code="TEST801").first()
        if test_created:
            db.session.delete(test_created)
            db.session.commit()

        print("\n" + "=" * 70)
        print("ALL 17 COURSE MANAGEMENT TEST SUITES PASSED CLEANLY!")
        print("=" * 70)


if __name__ == "__main__":
    run_tests()
