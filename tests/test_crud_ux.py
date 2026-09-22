import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import app
from models import User, Student, Faculty
from extensions import db

def run_tests():
    with app.app_context():
        client = app.test_client()

        print("=== 1. Authenticating as Admin ===")
        resp = client.post("/api/auth/login", json={"email": "admin@campus.edu", "password": "campus@123", "role": "admin"})
        assert resp.status_code == 200, f"Login failed: {resp.get_json()}"
        admin_headers = {"X-Session-Token": resp.get_json()["sessionToken"]}
        print("[PASS] Admin authenticated.")

        # Clean up any leftover test data
        old_stu = User.query.filter_by(email="test_ux_student@campus.edu").first()
        if old_stu:
            s = Student.query.filter_by(user_id=old_stu.id).first()
            if s:
                db.session.delete(s)
            db.session.delete(old_stu)
        old_fac = User.query.filter_by(email="ux_faculty@campus.edu").first()
        if old_fac:
            f = Faculty.query.filter_by(user_id=old_fac.id).first()
            if f:
                db.session.delete(f)
            db.session.delete(old_fac)
        db.session.commit()

        print("\n=== 2. Add Student ===")
        add_stu_payload = {
            "name": "Test Student UX",
            "email": "test_ux_student@campus.edu",
            "phone": "9876501234",
            "department": "Computer Science & Engineering",
            "year": "3rd Year",
            "semester": "6",
            "division": "B",
            "prn": "STU_UX_9999"
        }
        resp = client.post("/api/students", json=add_stu_payload, headers=admin_headers)
        assert resp.status_code == 201, f"Add student failed: {resp.get_json()}"
        stu_data = resp.get_json()["data"]
        stu_id = stu_data.get("studentCode") or stu_data.get("id")
        print(f"[PASS] Student created: {stu_id}")

        print("\n=== 3. Add Faculty ===")
        add_fac_payload = {
            "name": "Dr. UX Faculty",
            "email": "ux_faculty@campus.edu",
            "phone": "9876505678",
            "department": "Computer Science & Engineering",
            "designation": "Associate Professor",
            "facultyId": "FAC_UX_9999",
            "assignments": [
                {
                    "subject": "Database Management Systems",
                    "year": "3rd Year",
                    "semester": 6,
                    "divisions": ["A", "B"]
                }
            ]
        }
        resp = client.post("/api/faculty", json=add_fac_payload, headers=admin_headers)
        assert resp.status_code == 201, f"Add faculty failed: {resp.get_json()}"
        fac_data = resp.get_json()["data"]
        fac_id = fac_data.get("facultyCode") or fac_data.get("id")
        print(f"[PASS] Faculty created: {fac_id}")

        print("\n=== 4. Edit Student ===")
        edit_stu_payload = {"phone": "9876509999", "division": "A"}
        resp = client.put(f"/api/students/{stu_id}", json=edit_stu_payload, headers=admin_headers)
        assert resp.status_code == 200, f"Edit student failed: {resp.get_json()}"
        print("[PASS] Student profile updated.")

        print("\n=== 5. Post Notice & Event ===")
        resp = client.post("/api/notices", json={"title": "UX Test Notice", "category": "Academic", "body": "This is a test notice."}, headers=admin_headers)
        assert resp.status_code == 201
        notice_id = resp.get_json()["data"]["id"]
        print(f"[PASS] Notice created: ID {notice_id}")

        resp = client.post("/api/events", json={"title": "UX Test Hackathon", "date": "2026-10-15", "location": "Auditorium"}, headers=admin_headers)
        assert resp.status_code == 201
        event_id = resp.get_json()["data"]["id"]
        print(f"[PASS] Event created: ID {event_id}")

        print("\n=== 6. Cleanup Created Records ===")
        client.delete(f"/api/notices/{notice_id}", headers=admin_headers)
        client.delete(f"/api/events/{event_id}", headers=admin_headers)
        client.delete(f"/api/students/{stu_id}", headers=admin_headers)
        client.delete(f"/api/faculty/{fac_id}", headers=admin_headers)
        print("[PASS] Cleanup completed.")

        print("\n" + "=" * 70)
        print("ALL CRUD UX OPERATIONS PASSED!")
        print("=" * 70)

if __name__ == "__main__":
    run_tests()
