import sys
from pathlib import Path
from datetime import date

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app import create_app
from extensions import db
from models import User, Course, Student, AttendanceSession, AttendanceRecord, Result, Enrollment, FacultyAssignment


def run_acceptance_tests():
    print("=" * 75)
    print("RUNNING CAMPUS CONNECT ACCEPTANCE TESTS (REQUIREMENTS 37 - 42)")
    print("=" * 75)

    app = create_app()
    client = app.test_client()

    # -------------------------------------------------------------------------
    # REQUIREMENT 37: Admin Credential Verification (admin / admin)
    # -------------------------------------------------------------------------
    print("\n[REQ 37] Admin Credential Verification -> 'admin' / 'admin'")
    res = client.post("/api/auth/login", json={
        "username": "admin",
        "password": "admin",
        "role": "admin"
    })
    assert res.status_code == 200, f"Admin login failed: {res.get_json()}"
    admin_data = res.get_json()
    assert admin_data["success"] is True
    assert admin_data["data"]["role"] == "admin"
    admin_token = admin_data["sessionToken"]
    print("  [PASS] Successfully logged in with Username: admin, Password: admin, Role: admin")

    # -------------------------------------------------------------------------
    # REQUIREMENT 38: Faculty Login Test (amit.deshmukh@campus.edu / campus@123)
    # -------------------------------------------------------------------------
    print("\n[REQ 38] Faculty Login Test -> amit.deshmukh@campus.edu / campus@123")
    res = client.post("/api/auth/login", json={
        "email": "amit.deshmukh@campus.edu",
        "password": "campus@123",
        "role": "faculty"
    })
    assert res.status_code == 200, f"Faculty login failed: {res.get_json()}"
    fac_data = res.get_json()
    assert fac_data["success"] is True
    assert fac_data["data"]["role"] == "faculty"
    fac_token = fac_data["sessionToken"]
    print("  [PASS] Faculty logged in successfully.")

    # Faculty course dropdown: must ONLY show CS601
    res = client.get("/api/courses", headers={"X-Session-Token": fac_token})
    assert res.status_code == 200
    courses = res.get_json()["data"]
    course_codes = [c["code"] for c in courses]
    assert course_codes == ["CS601"], f"Expected only ['CS601'], got {course_codes}"
    print(f"  [PASS] Faculty course dropdown displays strictly assigned courses: {course_codes}")

    # Faculty roster: CS601 Div A -> exactly 20 students
    res = client.get("/api/attendance/roll-call?courseCode=CS601&division=A", headers={"X-Session-Token": fac_token})
    assert res.status_code == 200
    roster = res.get_json()["data"]["roster"]
    stu_codes = [s["studentId"] for s in roster if s["studentId"].startswith("STU2026")]
    assert len(stu_codes) == 20, f"Expected 20 CSE students (STU2026001 - STU2026020), found {len(stu_codes)}"
    print(f"  [PASS] CS601 Division A displays correct 20 enrolled students (STU2026001 - STU2026020).")

    # -------------------------------------------------------------------------
    # REQUIREMENT 39: Attendance Acceptance Test
    # -------------------------------------------------------------------------
    print("\n[REQ 39] Attendance Acceptance Test -> Mark & Verify Persistence")
    today_str = date.today().isoformat()
    # Mark Student 001 -> Present, Student 002 -> Absent, Student 003 -> Present
    rec_payload = [
        {"studentId": "STU2026001", "status": "present"},
        {"studentId": "STU2026002", "status": "absent"},
        {"studentId": "STU2026003", "status": "present"},
    ]
    res = client.post("/api/attendance/roll-call", json={
        "courseCode": "CS601",
        "division": "A",
        "date": today_str,
        "records": rec_payload
    }, headers={"X-Session-Token": fac_token})
    assert res.status_code == 200, f"Failed to mark attendance: {res.get_json()}"
    print("  [PASS] Saved attendance: Student 001 -> Present, Student 002 -> Absent, Student 003 -> Present")

    # Simulate page refresh
    res = client.get(f"/api/attendance/roll-call?courseCode=CS601&division=A&date={today_str}", headers={"X-Session-Token": fac_token})
    assert res.status_code == 200
    reloaded_roster = {s["studentId"]: s["status"] for s in res.get_json()["data"]["roster"]}
    assert reloaded_roster["STU2026001"] == "present"
    assert reloaded_roster["STU2026002"] == "absent"
    assert reloaded_roster["STU2026003"] == "present"
    print("  [PASS] Refresh verified: Attendance records remain perfectly saved in PostgreSQL!")

    # -------------------------------------------------------------------------
    # REQUIREMENT 40: Marks Acceptance Test
    # -------------------------------------------------------------------------
    print("\n[REQ 40] Marks Acceptance Test -> Enter Marks & Verify Persistence")
    res = client.post("/api/results", json={
        "studentId": "STU2026001",
        "courseCode": "CS601",
        "marks": 95
    }, headers={"X-Session-Token": fac_token})
    assert res.status_code in (200, 201), f"Failed to save marks: {res.get_json()}"
    saved_res = res.get_json()["data"]
    assert saved_res["total"] == 95.0
    assert saved_res["grade"] == "A+"
    print("  [PASS] Saved marks for Student 001 in CS601 (95/100, Grade A+)")

    # Simulate page refresh
    res = client.get("/api/results?courseCode=CS601&division=A", headers={"X-Session-Token": fac_token})
    assert res.status_code == 200
    res_list = res.get_json()["data"]
    stu1_res = next((r for r in res_list if r["studentId"] == "STU2026001"), None)
    assert stu1_res is not None, "Result for STU2026001 not found"
    assert stu1_res["total"] == 95.0
    print("  [PASS] Refresh verified: Marks remain saved and loaded in Results sheet!")

    # -------------------------------------------------------------------------
    # REQUIREMENT 41: Student Acceptance Test (student001@campus.edu / campus@123)
    # -------------------------------------------------------------------------
    print("\n[REQ 41] Student Acceptance Test -> student001@campus.edu / campus@123")
    res = client.post("/api/auth/login", json={
        "email": "student001@campus.edu",
        "password": "campus@123",
        "role": "student"
    })
    assert res.status_code == 200, f"Student login failed: {res.get_json()}"
    stu_data = res.get_json()
    stu_token = stu_data["sessionToken"]

    # Check Student endpoints
    # 1. Dashboard summary
    d_res = client.get("/api/dashboard/summary", headers={"X-Session-Token": stu_token})
    assert d_res.status_code == 200
    # 2. Courses
    c_res = client.get("/api/courses", headers={"X-Session-Token": stu_token})
    assert c_res.status_code == 200
    assert len(c_res.get_json()["data"]) in (6, 7), "Student must see their enrolled courses"
    # 3. Attendance Summary
    a_res = client.get("/api/attendance/summary", headers={"X-Session-Token": stu_token})
    assert a_res.status_code == 200
    # 4. Results
    r_res = client.get("/api/results/my", headers={"X-Session-Token": stu_token})
    assert r_res.status_code == 200
    # 5. Assignments
    asg_res = client.get("/api/assignments", headers={"X-Session-Token": stu_token})
    assert asg_res.status_code == 200
    # 6. Study Materials
    m_res = client.get("/api/materials", headers={"X-Session-Token": stu_token})
    assert m_res.status_code == 200
    # 7. Notices
    n_res = client.get("/api/notices", headers={"X-Session-Token": stu_token})
    assert n_res.status_code == 200
    # 8. Events
    e_res = client.get("/api/events", headers={"X-Session-Token": stu_token})
    assert e_res.status_code == 200
    # 9. Leave Requests
    l_res = client.get("/api/leaves", headers={"X-Session-Token": stu_token})
    assert l_res.status_code == 200

    # Student cannot view other student's data
    other_res = client.get("/api/students/STU2026002", headers={"X-Session-Token": stu_token})
    assert other_res.status_code == 403, f"Expected 403, got {other_res.status_code}"

    print("  [PASS] Student can view Courses, Attendance, Results, Assignments, Materials, Notices, Events, Leaves.")
    print("  [PASS] Privacy enforced: Student cannot view other students' private data (403 Forbidden).")

    # -------------------------------------------------------------------------
    # REQUIREMENT 42: Security Acceptance Test (Server-Side RBAC Enforcement)
    # -------------------------------------------------------------------------
    print("\n[REQ 42] Security Acceptance Test -> Manipulate API Parameters")
    # Amit Deshmukh is assigned to CS601 Div A.
    # Try 1: Access CS602 (assigned to Prof. Rajesh Verma) roll-call
    res = client.get("/api/attendance/roll-call?courseCode=CS602&division=A", headers={"X-Session-Token": fac_token})
    assert res.status_code == 403, f"Expected 403 for unauthorized course, got {res.status_code}"
    print("  [PASS] Faculty blocked from accessing other faculty's course (CS602): HTTP 403 Forbidden.")

    # Try 2: Access CS601 Division B (not assigned to Amit Deshmukh)
    res = client.get("/api/attendance/roll-call?courseCode=CS601&division=B", headers={"X-Session-Token": fac_token})
    assert res.status_code == 403, f"Expected 403 for unauthorized division, got {res.status_code}"
    print("  [PASS] Faculty blocked from accessing unassigned division (CS601 Div B): HTTP 403 Forbidden.")

    # Try 3: Save attendance for CS602
    res = client.post("/api/attendance/roll-call", json={
        "courseCode": "CS602",
        "division": "A",
        "records": [{"studentId": "STU2026001", "status": "present"}]
    }, headers={"X-Session-Token": fac_token})
    assert res.status_code == 403, f"Expected 403 for marking CS602, got {res.status_code}"
    print("  [PASS] Faculty blocked from saving attendance for unassigned course: HTTP 403 Forbidden.")

    # Try 4: Enter marks for CS602
    res = client.post("/api/results", json={
        "studentId": "STU2026001",
        "courseCode": "CS602",
        "marks": 85
    }, headers={"X-Session-Token": fac_token})
    assert res.status_code == 403, f"Expected 403 for entering marks in CS602, got {res.status_code}"
    print("  [PASS] Faculty blocked from entering marks for unassigned course: HTTP 403 Forbidden.")

    print("\n" + "=" * 75)
    print("ALL ACCEPTANCE TESTS (REQUIREMENTS 37 - 42) PASSED 100% CLEANLY!")
    print("=" * 75)


if __name__ == "__main__":
    run_acceptance_tests()
