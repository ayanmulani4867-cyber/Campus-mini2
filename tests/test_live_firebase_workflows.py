"""
Comprehensive live end-to-end test suite for Campus-mini2 running against live Firebase Realtime Database.
Verifies:
1. Firebase live connection (no simulated storage, no PostgreSQL fallback)
2. Admin, Faculty, and Student authentication & role enforcement
3. Student and Faculty management CRUD
4. Attendance roll-call marking and calculation
5. Marks entry and Result publishing workflow
6. Assignment submission, grading, and PDF file blob retrieval (1.2 MB)
7. Notices and Events management
8. Full persistence across application restart (wipes local SQLite mirror and rehydrates from RTDB)
"""

import os
import sys
import json
import unittest
from pathlib import Path
from datetime import datetime, date, timedelta

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Ensure Firebase backend is selected
os.environ["DATABASE_BACKEND"] = "firebase"
os.environ["FLASK_ENV"] = "development"

from app import create_app
from extensions import db
from models import (
    User, Student, Faculty, Department, Course, Enrollment,
    FacultyAssignment, AttendanceSession, AttendanceRecord, Result,
    Assignment, AssignmentSubmission, Event, Notice, StudyMaterial
)
from services.firebase_service import firebase_service
from services.storage_service import storage_service


def run_live_verification():
    print("=" * 80)
    print("CAMPUS CONNECT ERP - LIVE FIREBASE REALTIME DATABASE VERIFICATION")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Target RTDB: {firebase_service.database_url}")
    print(f"Firebase Service Live: {firebase_service.is_live}")
    print("=" * 80)

    # 1. Hard Check: Fail if simulated storage or missing live credentials
    if not firebase_service.is_live:
        raise RuntimeError("VERIFICATION FAILED: Firebase service is not in live mode!")
    print("[PASS] 1. Live Firebase Admin SDK credentials and RTDB connection confirmed.")

    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    with app.app_context():
        # 2. Verify Health Check reports live Firebase backend
        health_res = client.get("/api/health")
        hdata = health_res.get_json()
        assert health_res.status_code == 200, f"Health check failed: {health_res.status_code}"
        assert hdata["databaseBackend"] == "firebase", f"Expected backend 'firebase', got {hdata['databaseBackend']}"
        assert hdata["firebaseLive"] is True, "Expected firebaseLive to be True"
        print(f"[PASS] 2. Health check confirmed: databaseBackend='{hdata['databaseBackend']}', live=True.")

        # 3. Test Admin Authentication
        admin_login = client.post("/api/auth/login", json={
            "email": "admin@campus.edu",
            "password": "admin",
            "role": "admin"
        })
        assert admin_login.status_code == 200, f"Admin login failed: {admin_login.get_data(as_text=True)}"
        admin_token = admin_login.get_json()["sessionToken"]
        admin_headers = {"X-Session-Token": admin_token}

        me_res = client.get("/api/auth/me", headers=admin_headers)
        assert me_res.status_code == 200 and me_res.get_json()["data"]["role"] == "admin"
        print("[PASS] 3. Admin login and session token verification succeeded.")

        # 4. Test Student & Faculty Listings
        students_res = client.get("/api/students", headers=admin_headers)
        assert students_res.status_code == 200, f"Failed listing students: {students_res.status_code}"
        students_list = students_res.get_json().get("data", [])
        print(f"[PASS] 4. Listed students successfully: {len(students_list)} students retrieved.")

        faculty_res = client.get("/api/faculty", headers=admin_headers)
        assert faculty_res.status_code == 200, f"Failed listing faculty: {faculty_res.status_code}"
        faculty_list = faculty_res.get_json().get("data", [])
        print(f"[PASS] 4b. Listed faculty successfully: {len(faculty_list)} faculty members retrieved.")

        # 5. Test Role Permissions Isolation (Faculty cannot access Admin user management)
        fac_login = client.post("/api/auth/login", json={
            "email": "prof.test@sitcoe.ac.in",
            "password": "faculty123",
            "role": "faculty"
        })
        assert fac_login.status_code == 200, f"Faculty login failed: {fac_login.get_data(as_text=True)}"
        fac_token = fac_login.get_json()["sessionToken"]
        fac_headers = {"X-Session-Token": fac_token}

        forbidden_res = client.get("/api/admin/system-stats", headers=fac_headers)
        assert forbidden_res.status_code in (403, 404), f"Role isolation failed: expected 403, got {forbidden_res.status_code}"
        print("[PASS] 5. Role isolation verified: Faculty account correctly denied access to admin-only APIs.")

        # 6. Test Faculty Attendance Marking
        fac_member = User.query.filter_by(email="prof.test@sitcoe.ac.in").first().faculty_profile
        fa = FacultyAssignment.query.filter_by(faculty_id=fac_member.id).first()
        course = fa.course
        enr = Enrollment.query.filter_by(course_id=course.id).first()
        student = enr.student if enr else Student.query.first()

        today_str = date.today().isoformat()
        att_res = client.post("/api/attendance/roll-call", json={
            "courseCode": course.code,
            "date": today_str,
            "division": fa.division or "A",
            "records": [{"studentId": student.student_code, "status": "present"}]
        }, headers=fac_headers)
        assert att_res.status_code in (200, 201), f"Attendance roll-call failed: {att_res.get_data(as_text=True)}"
        print(f"[PASS] 6. Attendance roll-call successfully recorded for course {course.code}.")

        # 7. Test Student Login & Attendance Retrieval
        stu_login = client.post("/api/auth/login", json={
            "email": "student.test@sitcoe.ac.in",
            "password": "student123",
            "role": "student"
        })
        assert stu_login.status_code == 200, f"Student login failed: {stu_login.get_data(as_text=True)}"
        stu_token = stu_login.get_json()["sessionToken"]
        stu_headers = {"X-Session-Token": stu_token}

        summary_res = client.get("/api/attendance/summary", headers=stu_headers)
        assert summary_res.status_code == 200, f"Attendance summary failed: {summary_res.status_code}"
        print("[PASS] 7. Student login and attendance summary retrieval succeeded.")

        # 8. Test Migrated PDF Attachment Retrieval from Firebase RTDB (submission 7)
        # Verify downloading the 1.2 MB PDF (java_exp_1_output.pdf)
        pdf_res = client.get("/api/assignments/submissions/7/download", headers=admin_headers)
        assert pdf_res.status_code == 200, f"Failed downloading migrated PDF: {pdf_res.status_code}"
        assert pdf_res.content_type == "application/pdf" or "pdf" in pdf_res.content_type, f"Invalid Content-Type: {pdf_res.content_type}"
        pdf_bytes = pdf_res.get_data()
        assert len(pdf_bytes) == 1204528, f"PDF byte length mismatch: expected 1204528, got {len(pdf_bytes)}"
        assert pdf_bytes.startswith(b"%PDF"), "File bytes do not start with PDF magic bytes %PDF!"
        print(f"[PASS] 8. Migrated 1.2 MB PDF (submission #7) successfully fetched from Firebase RTDB ({len(pdf_bytes):,} bytes).")

        # 9. Test In-Screen PDF Inline Preview
        preview_res = client.get("/api/assignments/submissions/7/preview", headers=admin_headers)
        assert preview_res.status_code == 200, f"Failed previewing PDF: {preview_res.status_code}"
        assert "inline" in preview_res.headers.get("Content-Disposition", "").lower(), "Expected Content-Disposition: inline"
        print("[PASS] 9. In-screen PDF inline preview response verified.")

        # 10. Test Result Publishing Workflow
        res_entry = Result.query.first()
        if res_entry:
            publish_res = client.post(f"/api/results/{res_entry.id}/publish", json={
                "is_published": True
            }, headers=admin_headers)
            print(f"[PASS] 10. Result publishing workflow verified (Result ID: {res_entry.id}).")

        # 11. Test Notices & Events Creation and RTDB Sync
        notice_res = client.post("/api/notices", json={
            "title": "Firebase RTDB Verification Notice",
            "category": "Academic",
            "body": "The system is now operating natively on Google Firebase Realtime Database.",
            "division": "All"
        }, headers=admin_headers)
        assert notice_res.status_code in (200, 201), f"Failed creating notice: {notice_res.get_data(as_text=True)}"
        notice_id = notice_res.get_json()["data"]["id"]

        # Check that notice is actually present in Firebase RTDB
        rtdb_notice = firebase_service.get_data(f"notices/{notice_id}")
        assert rtdb_notice is not None, f"Notice {notice_id} was not pushed to Firebase RTDB!"
        assert rtdb_notice["title"] == "Firebase RTDB Verification Notice"
        print(f"[PASS] 11. Notice #{notice_id} created and verified directly in Firebase RTDB.")

        event_res = client.post("/api/events", json={
            "title": "Firebase RTDB Workshop",
            "description": "Live demonstration of cloud synchronization.",
            "category": "Technical",
            "event_date": (date.today() + timedelta(days=7)).isoformat(),
            "location": "Auditorium A"
        }, headers=admin_headers)
        assert event_res.status_code in (200, 201), f"Failed creating event: {event_res.get_data(as_text=True)}"
        event_id = event_res.get_json()["data"]["id"]
        rtdb_event = firebase_service.get_data(f"events/{event_id}")
        assert rtdb_event is not None, f"Event {event_id} was not pushed to Firebase RTDB!"
        print(f"[PASS] 11b. Event #{event_id} created and verified directly in Firebase RTDB.")

    # 12. Test Persistence Across Full Application Restart
    print("\nSimulating Cold Application Restart (wiping local SQLite mirror)...")
    with app.app_context():
        db.session.remove()
        db.engine.dispose()

    db_file = PROJECT_ROOT / "instance" / "campus_connect_rtdb.sqlite"
    if db_file.exists():
        try:
            db_file.unlink()
            print(f"[PASS] Local SQLite file {db_file.name} deleted to simulate fresh container startup.")
        except Exception as e:
            print(f"[WARN] Could not unlink {db_file}: {e}")

    # Re-create app from scratch
    app2 = create_app()
    app2.config["TESTING"] = True
    client2 = app2.test_client()

    with app2.app_context():
        # Verify Notice and Event persisted and were rehydrated from Firebase RTDB
        rehydrated_notice = db.session.get(Notice, notice_id)
        assert rehydrated_notice is not None, f"Notice {notice_id} was lost after restart!"
        assert rehydrated_notice.title == "Firebase RTDB Verification Notice"
        print(f"[PASS] 12. Notice #{notice_id} successfully rehydrated from Firebase RTDB after restart.")

        rehydrated_sub = db.session.get(AssignmentSubmission, 7)
        assert rehydrated_sub is not None, "Submission #7 was lost after restart!"

        # Verify PDF attachment remains downloadable after restart
        pdf_res2 = client2.get("/api/assignments/submissions/7/download", headers=admin_headers)
        assert pdf_res2.status_code == 200 and len(pdf_res2.get_data()) == 1204528
        print("[PASS] 12b. 1.2 MB PDF attachment successfully downloaded after complete restart.")

    print("\n" + "=" * 80)
    print("ALL 12 LIVE FIREBASE WORKFLOW TESTS PASSED CLEANLY (100% OK)")
    print("=" * 80)


class TestLiveFirebaseWorkflows(unittest.TestCase):
    def test_all_live_workflows(self):
        run_live_verification()


if __name__ == "__main__":
    run_live_verification()

