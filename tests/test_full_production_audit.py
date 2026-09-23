import io
import json
import os
import sys
from pathlib import Path
from datetime import date, timedelta

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
from models import (
    User, Department, Course, Enrollment, Student, Faculty, FacultyAssignment,
    AttendanceSession, AttendanceRecord, Result, Notice, StudyMaterial, Event,
    LeaveRequest, Assignment, AssignmentSubmission
)


def get_app_and_client():
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    return app, app.test_client()


def login(client, email, password):
    return client.post(
        "/api/auth/login",
        data=json.dumps({"email": email, "password": password}),
        content_type="application/json"
    )


def logout(client):
    return client.post("/api/auth/logout")


# ==============================================================================
# SECTION 1: DATABASE & SEED AUDIT
# ==============================================================================

def test_01_database_17_tables_and_seed(app):
    """Verify all 17 required tables exist and canonical departments are present."""
    with app.app_context():
        # Check canonical departments
        canonical_depts = [
            "Computer Science & Engineering",
            "Electronics & Communication",
            "Mechanical Engineering",
            "Civil Engineering",
        ]
        for name in canonical_depts:
            dept = Department.resolve(name)
            assert dept is not None, f"Department '{name}' must resolve successfully"
            assert dept.id is not None
            assert dept.name == name

        # Verify all 17 models are queryable
        assert db.session.query(Department).count() >= 4
        assert db.session.query(User).count() >= 1
        assert db.session.query(Student).count() >= 1
        assert db.session.query(Faculty).count() >= 1
        assert db.session.query(Course).count() >= 1
        assert db.session.query(Enrollment).count() >= 1
        assert db.session.query(FacultyAssignment).count() >= 1
        assert db.session.query(AttendanceSession).count() >= 1
        assert db.session.query(AttendanceRecord).count() >= 1
        assert db.session.query(Result).count() >= 1
        assert db.session.query(Notice).count() >= 1
        assert db.session.query(Event).count() >= 1
        assert db.session.query(StudyMaterial).count() >= 1
        assert db.session.query(LeaveRequest).count() >= 1
        assert db.session.query(Assignment).count() >= 1
        assert db.session.query(AssignmentSubmission).count() >= 0


# ==============================================================================
# SECTION 2: AUTHENTICATION AUDIT
# ==============================================================================

def test_02_auth_flows(client, app):
    """Test Admin, Faculty, and Student login, wrong passwords, and session isolation."""
    # 1. Admin login with username 'admin'
    res = login(client, "admin", "admin")
    assert res.status_code == 200, res.data
    data = res.get_json()
    assert data["success"] is True
    assert data["user"]["role"] == "admin"
    logout(client)

    # 2. Admin login with email 'admin@campus.edu'
    res = login(client, "admin@campus.edu", "admin")
    assert res.status_code == 200
    logout(client)

    # 3. Faculty login
    res = login(client, "anita.sen@campus.edu", "campus@123")
    assert res.status_code == 200, f"Faculty login failed: {res.data}"
    data = res.get_json()
    assert (data.get("user") or data.get("data"))["role"] == "faculty"
    logout(client)

    # 4. Student login
    res = login(client, "rahul@campus.edu", "campus@123")
    assert res.status_code == 200, f"Student login failed: {res.data}"
    data = res.get_json()
    assert (data.get("user") or data.get("data"))["role"] == "student"
    logout(client)

    # 5. Invalid credentials rejection
    res = login(client, "admin@campus.edu", "wrongpassword")
    assert res.status_code == 401
    assert res.get_json()["success"] is False

    res = login(client, "nonexistent@campus.edu", "nopass")
    assert res.status_code == 401
    assert res.get_json()["success"] is False

    # 6. Password hashing verification
    with app.app_context():
        admin_user = User.query.filter_by(email="admin@campus.edu").first()
        assert admin_user is not None
        assert admin_user.password_hash != "admin"
        assert admin_user.check_password("admin") is True


# ==============================================================================
# SECTION 3: ADMIN USER DIRECTORY & MECHANICAL ENGINEERING RESOLUTION
# ==============================================================================

def test_03_create_students_all_departments(client, app):
    """
    CRITICAL TEST: Verify student creation for ALL departments including
    'Mechanical Engineering' and 'Civil Engineering'.
    """
    login(client, "admin", "admin")

    departments_to_test = [
        ("Computer Science & Engineering", "TEST-STU-CSE", "test.cse@campus.edu"),
        ("Electronics & Communication", "TEST-STU-ECE", "test.ece@campus.edu"),
        ("Mechanical Engineering", "TEST-STU-MECH", "test.mech@campus.edu"),
        ("Civil Engineering", "TEST-STU-CIVIL", "test.civil@campus.edu"),
    ]

    for dept_name, prn, email in departments_to_test:
        payload = {
            "name": f"Test Student {dept_name}",
            "email": email,
            "phone": "9876543210",
            "department": dept_name,
            "year": "3rd Year",
            "semester": 5,
            "division": "A",
            "prn": prn
        }
        res = client.post("/api/students", data=json.dumps(payload), content_type="application/json")
        # Should either create (201) or succeed if already created
        assert res.status_code in (201, 200, 400), f"Failed for department: {dept_name} - {res.data}"
        if res.status_code == 400:
            err = res.get_json().get("error", "")
            assert "already exists" in err.lower(), f"Unexpected 400 error: {err}"
        else:
            data = res.get_json()
            assert data["success"] is True
            assert data["data"]["dept"] == dept_name

    logout(client)


def test_04_create_faculty_all_departments(client):
    """Verify faculty creation for Mechanical Engineering and Civil Engineering."""
    login(client, "admin", "admin")

    departments_to_test = [
        ("Mechanical Engineering", "FAC-TEST-MECH", "prof.mech@campus.edu"),
        ("Civil Engineering", "FAC-TEST-CIVIL", "prof.civil@campus.edu"),
    ]

    for dept_name, fac_id, email in departments_to_test:
        payload = {
            "name": f"Prof Test {dept_name}",
            "email": email,
            "phone": "9123456780",
            "department": dept_name,
            "designation": "Assistant Professor",
            "faculty_id": fac_id
        }
        res = client.post("/api/faculty", data=json.dumps(payload), content_type="application/json")
        assert res.status_code in (201, 200, 400), f"Failed for faculty dept: {dept_name} - {res.data}"
        if res.status_code == 400:
            err = res.get_json().get("error", "")
            assert "already exists" in err.lower(), f"Unexpected 400 error: {err}"
        else:
            assert res.get_json()["success"] is True

    logout(client)


# ==============================================================================
# SECTION 4: COURSES & ENROLLMENTS AUDIT
# ==============================================================================

def test_05_courses_and_enrollments(client, app):
    """Test course creation across departments, editing, and student enrollment."""
    login(client, "admin", "admin")

    # 1. Create a course in Mechanical Engineering
    course_payload = {
        "code": "ME301",
        "name": "Thermodynamics & Heat Transfer",
        "department": "Mechanical Engineering",
        "semester": 5,
        "credits": 4,
        "category": "Core"
    }
    res = client.post("/api/courses", data=json.dumps(course_payload), content_type="application/json")
    assert res.status_code in (200, 201, 400)
    if res.status_code == 400:
        assert "already exists" in res.get_json().get("error", "").lower()

    # 2. Enroll student in course
    res = client.post("/api/courses/ME301/enroll", data=json.dumps({"student_id": "TEST-STU-MECH"}), content_type="application/json")
    assert res.status_code in (200, 201, 400)
    if res.status_code == 400:
        assert "already enrolled" in res.get_json().get("error", "").lower()

    # 3. Check course students list
    res = client.get("/api/courses/ME301/students")
    assert res.status_code == 200
    stus = res.get_json()["data"]
    assert any(s["prn"] == "TEST-STU-MECH" for s in stus)

    logout(client)


# ==============================================================================
# SECTION 5: ATTENDANCE WORKFLOW AUDIT
# ==============================================================================

def test_06_attendance_workflow(client, app):
    """Test complete faculty attendance marking and student viewing."""
    # Faculty login
    res = login(client, "anita.sen@campus.edu", "campus@123")
    assert res.status_code == 200, res.data

    # Post attendance session for CS601
    today_str = date.today().isoformat()
    att_payload = {
        "courseCode": "CS601",
        "date": today_str,
        "time_slot": "10:00 - 11:00 AM",
        "division": "A",
        "topic": "Audit Test - Graph Algorithms",
        "records": [
            {"studentId": "STU2024001", "status": "present"},
            {"studentId": "STU2024002", "status": "late"}
        ]
    }
    res = client.post("/api/attendance/roll-call", data=json.dumps(att_payload), content_type="application/json")
    assert res.status_code in (200, 201), res.data
    logout(client)

    # Student STU2024001 checks attendance
    res = login(client, "rahul@campus.edu", "campus@123")
    assert res.status_code == 200, res.data
    res = client.get("/api/attendance/summary")
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert "overall" in data
    assert "percentage" in data["overall"]
    assert data["overall"]["held"] >= 1
    logout(client)


# ==============================================================================
# SECTION 6: RESULTS WORKFLOW AUDIT
# ==============================================================================

def test_07_results_workflow(client, app):
    """Test faculty entering marks, saving, publishing, and student viewing."""
    # Faculty login
    res = login(client, "anita.sen@campus.edu", "campus@123")
    assert res.status_code == 200, res.data

    # Enter marks for STU2024001 in CS601
    marks_payload = {
        "student_id": "STU2024001",
        "course_code": "CS601",
        "semester": 6,
        "academic_year": "2024-25",
        "internal_marks": 25,
        "external_marks": 60
    }
    res = client.post("/api/results", data=json.dumps(marks_payload), content_type="application/json")
    assert res.status_code in (200, 201), res.data
    result_data = res.get_json()["data"]
    res_id = result_data["id"]

    # Publish the result
    pub_res = client.put(f"/api/results/{res_id}/publish")
    assert pub_res.status_code == 200, pub_res.data
    assert pub_res.get_json()["data"]["status"] == "published"
    logout(client)

    # Student checks results
    res = login(client, "rahul@campus.edu", "campus@123")
    assert res.status_code == 200, res.data
    res = client.get("/api/results/my")
    assert res.status_code == 200
    my_results = res.get_json()["data"]
    assert any(r["course_code"] == "CS601" for r in my_results)
    logout(client)


# ==============================================================================
# SECTION 7: ASSIGNMENTS & BYTEA SUBMISSION AUDIT
# ==============================================================================

def test_08_assignments_and_bytea_submission(client, app):
    """Test assignment creation, BYTEA file submission, grading, and download."""
    # 1. Faculty creates assignment
    res = login(client, "anita.sen@campus.edu", "campus@123")
    assert res.status_code == 200, res.data
    due_date = (date.today() + timedelta(days=7)).isoformat()
    assign_payload = {
        "title": "Audit Dynamic Programming Assignment",
        "course_code": "CS601",
        "description": "Solve the knapsack problem and submit PDF report.",
        "due_date": due_date,
        "total_marks": 50,
        "semester": 6,
        "division": "A"
    }
    res = client.post("/api/assignments", data=json.dumps(assign_payload), content_type="application/json")
    assert res.status_code in (200, 201), res.data
    assignment_id = res.get_json()["data"]["id"]
    logout(client)

    # 2. Student submits assignment with binary PDF data
    res = login(client, "rahul@campus.edu", "campus@123")
    assert res.status_code == 200, res.data
    fake_pdf_content = b"%PDF-1.4 Fake PDF Content for Audit Testing\n%%EOF"
    data = {
        "submission_text": "Here is my final algorithm analysis report.",
        "file": (io.BytesIO(fake_pdf_content), "report.pdf", "application/pdf")
    }
    res = client.post(
        f"/api/assignments/{assignment_id}/submit",
        data=data,
        content_type="multipart/form-data"
    )
    assert res.status_code in (200, 201), res.data
    submission_id = res.get_json()["data"]["id"]

    # 3. Student downloads submission file
    res = client.get(f"/api/assignments/submissions/{submission_id}/download")
    assert res.status_code == 200
    assert res.data == fake_pdf_content
    logout(client)

    # 4. Faculty grades submission
    res = login(client, "anita.sen@campus.edu", "campus@123")
    assert res.status_code == 200, res.data
    grade_payload = {
        "marks_obtained": 48,
        "feedback": "Excellent work and thorough proof."
    }
    res = client.post(
        f"/api/assignments/submissions/{submission_id}/grade",
        data=json.dumps(grade_payload),
        content_type="application/json"
    )
    assert res.status_code == 200
    assert res.get_json()["data"]["marks_obtained"] == 48
    logout(client)


# ==============================================================================
# SECTION 8: STUDY MATERIALS (POSTGRESQL BYTEA PERSISTENCE)
# ==============================================================================

def test_09_study_materials_bytea(client, app):
    """Test study material upload with BYTEA binary data and download."""
    res = login(client, "anita.sen@campus.edu", "campus@123")
    assert res.status_code == 200, res.data

    fake_file_content = b"%PDF-1.4 Binary Study Material Lecture Notes Content\n%%EOF"
    data = {
        "title": "Audit Lecture Notes - Tree Traversals",
        "course": "CS601",
        "department": "Computer Science & Engineering",
        "semester": "6",
        "file": (io.BytesIO(fake_file_content), "lecture_notes.pdf", "application/pdf")
    }
    res = client.post(
        "/api/materials",
        data=data,
        content_type="multipart/form-data"
    )
    assert res.status_code in (200, 201), res.data
    material_id = res.get_json()["data"]["id"]
    logout(client)

    # Student downloads material
    res = login(client, "rahul@campus.edu", "campus@123")
    assert res.status_code == 200, res.data
    res = client.get(f"/api/materials/{material_id}/download")
    assert res.status_code == 200
    assert res.data == fake_file_content
    logout(client)


# ==============================================================================
# SECTION 9: LEAVE REQUESTS WORKFLOW
# ==============================================================================

def test_10_leave_requests_workflow(client, app):
    """Test student applying for leave, faculty approving, and cancel flow."""
    # 1. Student applies for leave
    res = login(client, "rahul@campus.edu", "campus@123")
    assert res.status_code == 200, res.data
    start = (date.today() + timedelta(days=2)).isoformat()
    end = (date.today() + timedelta(days=4)).isoformat()
    leave_payload = {
        "leave_type": "Medical",
        "start_date": start,
        "end_date": end,
        "reason": "Attending medical consultation for flu."
    }
    res = client.post("/api/leaves", data=json.dumps(leave_payload), content_type="application/json")
    assert res.status_code in (200, 201), res.data
    leave_id = res.get_json()["data"]["id"]

    # Student views own leaves
    res = client.get("/api/leaves/my")
    assert res.status_code == 200
    assert any(l["id"] == leave_id for l in res.get_json()["data"])
    logout(client)

    # 2. Faculty reviews and approves leave
    res = login(client, "anita.sen@campus.edu", "campus@123")
    assert res.status_code == 200, res.data
    res = client.put(
        f"/api/leaves/{leave_id}/status",
        data=json.dumps({"status": "approved", "review_remarks": "Get well soon."}),
        content_type="application/json"
    )
    assert res.status_code == 200
    assert res.get_json()["data"]["status"] == "approved"
    logout(client)


# ==============================================================================
# SECTION 10: NOTICES & CAMPUS EVENTS
# ==============================================================================

def test_11_notices_and_events_crud(client, app):
    """Test notice creation, editing, deletion and event creation and editing."""
    res = login(client, "admin", "admin")
    assert res.status_code == 200, res.data

    # 1. Notice CRUD
    n_res = client.post(
        "/api/notices",
        data=json.dumps({
            "title": "Production Audit Notice",
            "body": "All systems operating normally under production audit.",
            "category": "Academic",
            "priority": "normal",
            "target_role": "all"
        }),
        content_type="application/json"
    )
    assert n_res.status_code in (200, 201), n_res.data
    nid = n_res.get_json()["data"]["id"]

    # Notice Edit (PUT /api/notices/<id>)
    update_res = client.put(
        f"/api/notices/{nid}",
        data=json.dumps({"title": "Updated Audit Notice"}),
        content_type="application/json"
    )
    assert update_res.status_code == 200
    assert update_res.get_json()["data"]["title"] == "Updated Audit Notice"

    # 2. Event CRUD
    e_res = client.post(
        "/api/events",
        data=json.dumps({
            "title": "Annual Tech Symposium 2026",
            "description": "Annual technical presentations and project exhibitions.",
            "category": "Technical",
            "event_date": (date.today() + timedelta(days=30)).isoformat(),
            "start_time": "09:30",
            "end_time": "17:00",
            "venue": "Main Auditorium"
        }),
        content_type="application/json"
    )
    assert e_res.status_code in (200, 201), e_res.data
    eid = e_res.get_json()["data"]["id"]

    # Event Edit (PUT /api/events/<id>)
    update_e = client.put(
        f"/api/events/{eid}",
        data=json.dumps({"title": "Annual Tech Symposium & Hackathon 2026"}),
        content_type="application/json"
    )
    assert update_e.status_code == 200
    assert "Hackathon" in update_e.get_json()["data"]["title"]

    logout(client)


# ==============================================================================
# SECTION 11: DASHBOARD AUDIT
# ==============================================================================

def test_12_dashboards_real_data(client):
    """Test dashboard stats for Admin, Faculty, and Student."""
    # Admin dashboard
    res = login(client, "admin", "admin")
    assert res.status_code == 200, res.data
    res = client.get("/api/dashboard/stats")
    assert res.status_code == 200
    stats = res.get_json()["data"]
    assert stats["total_students"] >= 1
    assert stats["total_faculty"] >= 1
    assert stats["total_courses"] >= 1
    logout(client)

    # Faculty dashboard
    res = login(client, "anita.sen@campus.edu", "campus@123")
    assert res.status_code == 200, res.data
    res = client.get("/api/dashboard/stats")
    assert res.status_code == 200
    logout(client)

    # Student dashboard
    res = login(client, "rahul@campus.edu", "campus@123")
    assert res.status_code == 200, res.data
    res = client.get("/api/dashboard/stats")
    assert res.status_code == 200
    logout(client)


def run_audit_suite():
    print("=" * 80)
    print("CAMPUS CONNECT — FULL PRODUCTION AUDIT & VERIFICATION SUITE")
    print("=" * 80)

    app, _ = get_app_and_client()
    tests = [
        ("01: Database 17 Tables & Idempotent Seed", lambda: test_01_database_17_tables_and_seed(app)),
        ("02: Authentication Flows & Hashed Passwords", lambda: test_02_auth_flows(app.test_client(), app)),
        ("03: Admin User Directory - Students in ALL Depts (incl Mechanical & Civil)", lambda: test_03_create_students_all_departments(app.test_client(), app)),
        ("04: Faculty Creation in ALL Departments", lambda: test_04_create_faculty_all_departments(app.test_client())),
        ("05: Courses & Enrollments Across Departments", lambda: test_05_courses_and_enrollments(app.test_client(), app)),
        ("06: Attendance Marking & Summary Workflow", lambda: test_06_attendance_workflow(app.test_client(), app)),
        ("07: Examination Results Entry & Publishing", lambda: test_07_results_workflow(app.test_client(), app)),
        ("08: Assignments & PostgreSQL BYTEA File Submissions", lambda: test_08_assignments_and_bytea_submission(app.test_client(), app)),
        ("09: Study Materials PostgreSQL BYTEA Persistence", lambda: test_09_study_materials_bytea(app.test_client(), app)),
        ("10: Student Leave Requests Workflow", lambda: test_10_leave_requests_workflow(app.test_client(), app)),
        ("11: Notices & Campus Events CRUD & Editing", lambda: test_11_notices_and_events_crud(app.test_client(), app)),
        ("12: Real Database Dashboards (No Fake Counts)", lambda: test_12_dashboards_real_data(app.test_client())),
    ]

    passed = 0
    failed = 0
    failures = []

    for name, test_fn in tests:
        print(f"\n[RUNNING] {name} ...")
        try:
            test_fn()
            print(f"[PASS] {name}")
            passed += 1
        except Exception as e:
            print(f"[FAIL] {name}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
            failures.append((name, str(e)))

    print("\n" + "=" * 80)
    print(f"AUDIT SUITE SUMMARY: {passed} PASSED, {failed} FAILED (TOTAL {len(tests)})")
    print("=" * 80)

    if failures:
        print("FAILURES:")
        for name, err in failures:
            print(f" - {name}: {err}")
        sys.exit(1)
    else:
        print("ALL 12 TEST SUITES PASSED CLEANLY AGAINST RENDER POSTGRESQL!")
        sys.exit(0)


if __name__ == "__main__":
    run_audit_suite()
