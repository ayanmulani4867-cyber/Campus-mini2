import json
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import app

def run_tests():
    print("=" * 70)
    print("TESTING ADMIN NAVIGATION, ROUTES & MODULE INTEGRATION")
    print("=" * 70)

    client = app.test_client()

    # 1. Admin Login
    resp = client.post("/api/auth/login", json={
        "email": "admin@campus.edu",
        "password": "campus@123",
        "role": "admin"
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.get_json()}"
    res = resp.get_json()
    admin_token = res["sessionToken"]
    headers = {"X-Session-Token": admin_token}
    print("[PASS] Admin logged in successfully.")

    # 2. Check User Directory APIs
    resp = client.get("/api/students", headers=headers)
    assert resp.status_code == 200, f"Failed to get students: {resp.get_json()}"
    students_res = resp.get_json()
    assert students_res["success"], "Students API not success"
    print(f"[PASS] /api/students returned {len(students_res['data'])} student records.")

    resp = client.get("/api/faculty", headers=headers)
    assert resp.status_code == 200, f"Failed to get faculty: {resp.get_json()}"
    faculty_res = resp.get_json()
    assert faculty_res["success"], "Faculty API not success"
    print(f"[PASS] /api/faculty returned {len(faculty_res['data'])} faculty records.")

    # 3. Check Results API
    resp = client.get("/api/results", headers=headers)
    assert resp.status_code == 200, f"Failed to get results: {resp.get_json()}"
    results_res = resp.get_json()
    assert results_res["success"], "Results API not success"
    print(f"[PASS] /api/results returned {len(results_res['data'])} result records.")

    # 4. Check Materials API
    resp = client.get("/api/materials", headers=headers)
    assert resp.status_code == 200, f"Failed to get materials: {resp.get_json()}"
    materials_res = resp.get_json()
    assert materials_res["success"], "Materials API not success"
    print(f"[PASS] /api/materials returned {len(materials_res['data'])} material records.")

    # 5. Check Dashboard Summary
    resp = client.get("/api/dashboard/summary", headers=headers)
    assert resp.status_code == 200, f"Failed to get dashboard summary: {resp.get_json()}"
    dash_res = resp.get_json()
    assert dash_res["success"], "Dashboard API not success"
    metrics = dash_res.get("data", {}).get("metrics", {})
    print(f"[PASS] /api/dashboard/summary returned metrics: {metrics}")

    # 6. Check Notices API
    resp = client.get("/api/notices", headers=headers)
    assert resp.status_code == 200, f"Failed to get notices: {resp.get_json()}"
    notices_res = resp.get_json()
    assert notices_res["success"], "Notices API not success"
    print(f"[PASS] /api/notices returned {len(notices_res['data'])} notices.")

    # 7. Check Events API
    resp = client.get("/api/events", headers=headers)
    assert resp.status_code == 200, f"Failed to get events: {resp.get_json()}"
    events_res = resp.get_json()
    assert events_res["success"], "Events API not success"
    print(f"[PASS] /api/events returned {len(events_res['data'])} events.")

    # 8. Check Courses API
    resp = client.get("/api/courses", headers=headers)
    assert resp.status_code == 200, f"Failed to get courses: {resp.get_json()}"
    courses_res = resp.get_json()
    assert courses_res["success"], "Courses API not success"
    print(f"[PASS] /api/courses returned {len(courses_res['data'])} courses.")

    # 9. Check Departments API
    resp = client.get("/api/departments", headers=headers)
    assert resp.status_code == 200, f"Failed to get departments: {resp.get_json()}"
    dept_res = resp.get_json()
    assert dept_res["success"], "Departments API not success"
    print(f"[PASS] /api/departments returned {len(dept_res['data'])} departments.")

    print("=" * 70)
    print("ALL ADMIN NAVIGATION & API CHECKS PASSED!")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()
