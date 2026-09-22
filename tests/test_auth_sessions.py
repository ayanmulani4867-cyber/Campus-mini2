import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app import app
from models import UserSession


def run_tests():
    print("\n" + "=" * 70)
    print("RUNNING CAMPUS CONNECT MULTI-TAB AUTH & ROLE ISOLATION SUITE")
    print("=" * 70)

    client = app.test_client()

    # -------------------------------------------------------------------------
    # TEST 1: Unauthenticated Requests return 401
    # -------------------------------------------------------------------------
    print("\n[TEST 1] Testing Unauthenticated Access -> Expect 401")
    res = client.get("/api/auth/me")
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"
    print("  [PASS] /api/auth/me without token/cookie correctly returned 401 Unauthorized.")

    res = client.get("/api/students")
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"
    print("  [PASS] /api/students without auth correctly returned 401 Unauthorized.")

    # -------------------------------------------------------------------------
    # TEST 2: Tab 1 - Admin Login & Session Generation
    # -------------------------------------------------------------------------
    print("\n[TEST 2] Tab 1: Admin Login -> Expect 200, role='admin', sessionToken")
    res = client.post("/api/auth/login", json={
        "email": "admin@campus.edu",
        "password": "campus@123",
        "role": "admin"
    })
    assert res.status_code == 200, f"Login failed: {res.get_json()}"
    admin_data = res.get_json()
    admin_token = admin_data.get("sessionToken")
    assert admin_token, "sessionToken missing from admin login response"
    assert admin_data["data"]["role"] == "admin"
    print(f"  [PASS] Admin logged in. Received Tab 1 sessionToken: {admin_token[:12]}...")

    # Verify Tab 1 Me
    res = client.get("/api/auth/me", headers={"X-Session-Token": admin_token})
    assert res.status_code == 200
    assert res.get_json()["data"]["email"] == "admin@campus.edu"
    print("  [PASS] Tab 1 /api/auth/me verified as Admin.")

    # -------------------------------------------------------------------------
    # TEST 3: Tab 2 - Student Login in Same Browser Window
    # -------------------------------------------------------------------------
    print("\n[TEST 3] Tab 2: Student Login -> Expect 200, role='student', separate sessionToken")
    res = client.post("/api/auth/login", json={
        "email": "rahul@campus.edu",
        "password": "campus@123",
        "role": "student"
    })
    assert res.status_code == 200, f"Login failed: {res.get_json()}"
    student_data = res.get_json()
    student_token = student_data.get("sessionToken")
    assert student_token, "sessionToken missing from student login response"
    assert student_token != admin_token, "Student and Admin must have distinct tokens"
    assert student_data["data"]["role"] == "student"
    print(f"  [PASS] Student logged in. Received Tab 2 sessionToken: {student_token[:12]}...")

    # Verify Tab 2 Me
    res = client.get("/api/auth/me", headers={"X-Session-Token": student_token})
    assert res.status_code == 200
    assert res.get_json()["data"]["email"] == "rahul@campus.edu"
    print("  [PASS] Tab 2 /api/auth/me verified as Student.")

    # -------------------------------------------------------------------------
    # TEST 4: Tab 1 Refresh Isolation (Admin must NOT become Student!)
    # -------------------------------------------------------------------------
    print("\n[TEST 4] Tab 1 Refresh: Refreshing Admin after Student Login")
    res = client.get("/api/auth/me", headers={"X-Session-Token": admin_token})
    assert res.status_code == 200
    tab1_user = res.get_json()["data"]
    assert tab1_user["email"] == "admin@campus.edu", f"Tab 1 corrupted! Got {tab1_user['email']}"
    assert tab1_user["role"] == "admin", f"Tab 1 role corrupted! Got {tab1_user['role']}"
    print("  [PASS] Tab 1 refreshed: STILL Admin (No interference from Tab 2 Student login!).")

    # Verify Tab 1 Dashboard Summary
    res = client.get("/api/dashboard/summary", headers={"X-Session-Token": admin_token})
    assert res.status_code == 200
    assert "facultyMembers" in res.get_json()["data"], "Admin dashboard data missing"
    print("  [PASS] Tab 1 Dashboard Summary returned Admin metrics.")

    # Verify Tab 2 Dashboard Summary
    res = client.get("/api/dashboard/summary", headers={"X-Session-Token": student_token})
    assert res.status_code == 200
    assert "attendancePct" in res.get_json()["data"], "Student dashboard data missing"
    assert "facultyMembers" not in res.get_json()["data"], "Student dashboard leaked Admin metrics!"
    print("  [PASS] Tab 2 Dashboard Summary returned Student metrics.")

    # -------------------------------------------------------------------------
    # TEST 5: Tab 3 - Faculty Login & Isolation
    # -------------------------------------------------------------------------
    print("\n[TEST 5] Tab 3: Faculty Login & Isolation")
    res = client.post("/api/auth/login", json={
        "email": "anita.sen@campus.edu",
        "password": "campus@123",
        "role": "faculty"
    })
    assert res.status_code == 200
    faculty_token = res.get_json().get("sessionToken")
    assert faculty_token
    print(f"  [PASS] Faculty logged in. Received Tab 3 sessionToken: {faculty_token[:12]}...")

    # Check all 3 tabs simultaneously
    res_admin = client.get("/api/auth/me", headers={"X-Session-Token": admin_token})
    res_student = client.get("/api/auth/me", headers={"X-Session-Token": student_token})
    res_faculty = client.get("/api/auth/me", headers={"X-Session-Token": faculty_token})

    assert res_admin.get_json()["data"]["role"] == "admin"
    assert res_student.get_json()["data"]["role"] == "student"
    assert res_faculty.get_json()["data"]["role"] == "faculty"
    print("  [PASS] Simultaneous 3-way session verification succeeded: Tab 1=Admin, Tab 2=Student, Tab 3=Faculty.")

    # -------------------------------------------------------------------------
    # TEST 6: Strict Role Authorization (RBAC) Checks
    # -------------------------------------------------------------------------
    print("\n[TEST 6] Strict Server-Side Role Authorization (RBAC)")

    # 6a. Student cannot access Admin User Directory
    res = client.get("/api/students", headers={"X-Session-Token": student_token})
    assert res.status_code == 403, f"Expected 403 for student accessing /api/students, got {res.status_code}"
    print("  [PASS] Student GET /api/students -> 403 Forbidden.")

    res = client.post("/api/students", headers={"X-Session-Token": student_token}, json={"name": "Hacker"})
    assert res.status_code == 403, f"Expected 403 for student POST /api/students, got {res.status_code}"
    print("  [PASS] Student POST /api/students -> 403 Forbidden.")

    res = client.get("/api/faculty", headers={"X-Session-Token": student_token})
    assert res.status_code == 403, f"Expected 403 for student accessing /api/faculty, got {res.status_code}"
    print("  [PASS] Student GET /api/faculty -> 403 Forbidden.")

    # 6b. Faculty cannot access Admin User Directory or Admin routes
    res = client.get("/api/students", headers={"X-Session-Token": faculty_token})
    assert res.status_code == 403, f"Expected 403 for faculty accessing /api/students, got {res.status_code}"
    print("  [PASS] Faculty GET /api/students -> 403 Forbidden.")

    res = client.post("/api/departments", headers={"X-Session-Token": faculty_token}, json={"name": "New Dept"})
    assert res.status_code == 403, f"Expected 403 for faculty POST /api/departments, got {res.status_code}"
    print("  [PASS] Faculty POST /api/departments -> 403 Forbidden.")

    # 6c. Admin can access Admin User Directory
    res = client.get("/api/students", headers={"X-Session-Token": admin_token})
    assert res.status_code == 200, f"Expected 200 for admin GET /api/students, got {res.status_code}"
    print(f"  [PASS] Admin GET /api/students -> 200 OK ({len(res.get_json()['data'])} students).")

    # 6d. Admin cannot access Faculty-only Classroom Roll-Call
    res = client.get("/api/attendance/roll-call?courseCode=CS301&division=A", headers={"X-Session-Token": admin_token})
    assert res.status_code == 403, f"Expected 403 for admin GET roll-call, got {res.status_code}"
    print("  [PASS] Admin GET /api/attendance/roll-call -> 403 Forbidden (Roll-call is reserved for Faculty).")

    # 6e. Faculty CAN access Classroom Roll-Call
    res = client.get("/api/attendance/roll-call?courseCode=CS301&division=A", headers={"X-Session-Token": faculty_token})
    assert res.status_code in (200, 404), f"Unexpected status for faculty roll-call: {res.status_code}"
    print("  [PASS] Faculty authorized for /api/attendance/roll-call.")

    # 6f. Student cannot view other students' profiles
    res = client.get("/api/students/STU2024002", headers={"X-Session-Token": student_token})
    assert res.status_code in (403, 404), f"Expected 403/404 for student viewing other student, got {res.status_code}"
    print("  [PASS] Student cannot view other student's profile.")

    # -------------------------------------------------------------------------
    # TEST 7: Role Tampering Immunity
    # -------------------------------------------------------------------------
    print("\n[TEST 7] Testing Client-Side Role Tampering Immunity")
    # Sending a student session token with fake header or fake body claiming to be admin
    res = client.post("/api/students",
                      headers={"X-Session-Token": student_token, "X-Role": "admin"},
                      json={"name": "Imposter", "role": "admin"})
    assert res.status_code == 403, "Tampering attempt bypassed authorization!"
    print("  [PASS] Client cannot bypass authorization by supplying fake role headers or payloads.")

    # -------------------------------------------------------------------------
    # TEST 8: Scoped Logout Isolation
    # -------------------------------------------------------------------------
    print("\n[TEST 8] Scoped Logout Isolation: Logging out Student in Tab 2")
    res = client.post("/api/auth/logout", headers={"X-Session-Token": student_token})
    assert res.status_code == 200
    print("  [PASS] Tab 2 logout call succeeded.")

    # Verify Tab 2 is now logged out
    res = client.get("/api/auth/me", headers={"X-Session-Token": student_token})
    assert res.status_code == 401, f"Expected 401 for revoked student token, got {res.status_code}"
    print("  [PASS] Tab 2 Student token is now revoked (returned 401 Unauthorized).")

    # Verify Tab 1 Admin is STILL LOGGED IN
    res = client.get("/api/auth/me", headers={"X-Session-Token": admin_token})
    assert res.status_code == 200, f"Tab 1 Admin was prematurely logged out! Got {res.status_code}"
    assert res.get_json()["data"]["role"] == "admin"
    print("  [PASS] Tab 1 Admin session is STILL ACTIVE and authenticated after Student logout!")

    # Verify Tab 3 Faculty is STILL LOGGED IN
    res = client.get("/api/auth/me", headers={"X-Session-Token": faculty_token})
    assert res.status_code == 200
    assert res.get_json()["data"]["role"] == "faculty"
    print("  [PASS] Tab 3 Faculty session is STILL ACTIVE and authenticated!")

    print("\n" + "=" * 70)
    print("ALL MULTI-TAB AUTH & ROLE ISOLATION TESTS PASSED (100% SUCCESS)!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run_tests()
