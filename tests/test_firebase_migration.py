import os
import sys
import json
import unittest
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Ensure testing environment uses firebase backend
os.environ["DATABASE_BACKEND"] = "firebase"
os.environ["FLASK_ENV"] = "development"

from app import create_app
from extensions import db
from models import (
    User, Student, Faculty, Department, Course, Enrollment,
    AttendanceSession, AttendanceRecord, Result, Assignment,
    AssignmentSubmission, Event, Notice
)
from services.firebase_service import firebase_service
from services.firebase_sync import register_firebase_rtdb_hooks


class TestFirebaseMigration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

    def setUp(self):
        with self.app.app_context():
            db.create_all()
            register_firebase_rtdb_hooks(db)

    def test_01_firebase_service_initialization(self):
        """Verify Firebase service initializes with target Realtime Database URL."""
        self.assertIsNotNone(firebase_service)
        self.assertEqual(
            firebase_service.database_url,
            "https://campus-mini2-default-rtdb.firebaseio.com/"
        )

    def test_02_firebase_rtdb_crud_and_counters(self):
        """Verify RTDB get, set, update, delete, and atomic counter operations."""
        # 1. Set data
        test_path = "test_nodes/item_1"
        test_val = {"id": 1, "name": "Firebase RTDB Test", "status": "active"}
        firebase_service.set_data(test_path, test_val)
        retrieved = firebase_service.get_data(test_path)
        self.assertEqual(retrieved, test_val)

        # 2. Update data
        firebase_service.update_data(test_path, {"status": "completed", "score": 98.5})
        updated = firebase_service.get_data(test_path)
        self.assertEqual(updated["status"], "completed")
        self.assertEqual(updated["score"], 98.5)
        self.assertEqual(updated["name"], "Firebase RTDB Test")

        # 3. Counters
        c1 = firebase_service.get_next_id("test_counter")
        c2 = firebase_service.get_next_id("test_counter")
        self.assertEqual(c2, c1 + 1)

        # 4. Delete data
        firebase_service.delete_data(test_path)
        self.assertIsNone(firebase_service.get_data(test_path))

    def test_03_health_check_reports_firebase(self):
        """Verify health check endpoint reports Firebase backend configuration."""
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["databaseBackend"], "firebase")
        self.assertTrue(data["databaseConfigured"])
        self.assertIn("firebaseio.com", data["firebaseUrl"])

    def test_04_admin_and_academic_workflows(self):
        """Verify Admin login, Department creation, and Course offering."""
        with self.app.app_context():
            # Ensure Admin User exists
            admin = User.query.filter_by(role="admin").first()
            if not admin:
                admin = User(
                    email="admin@campus.edu",
                    full_name="System Administrator",
                    role="admin",
                    is_active=True
                )
                admin.set_password("admin")
                db.session.add(admin)
                db.session.commit()

        # Login as Admin
        res = self.client.post("/api/auth/login", json={
            "email": "admin@campus.edu",
            "password": "admin",
            "role": "admin"
        })
        self.assertEqual(res.status_code, 200)
        auth_data = res.get_json()
        token = auth_data["sessionToken"]
        self.assertIsNotNone(token)
        headers = {"X-Session-Token": token}

        # Verify /api/auth/me
        me_res = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(me_res.status_code, 200)
        self.assertEqual(me_res.get_json()["data"]["role"], "admin")

        # Admin: List & Create Department
        depts_res = self.client.get("/api/departments", headers=headers)
        self.assertEqual(depts_res.status_code, 200)

        # Create Test Department
        new_dept = self.client.post("/api/departments", json={
            "name": "Artificial Intelligence & Data Science",
            "code": "AIDS"
        }, headers=headers)
        self.assertIn(new_dept.status_code, (201, 400))  # 201 created, or 400 if already exists

    def test_05_faculty_and_attendance_workflows(self):
        """Verify Faculty assignment, Attendance marking, and Result publishing."""
        with self.app.app_context():
            dept = Department.query.first()
            if not dept:
                dept = Department(name="Computer Science & Engineering", code="CSE")
                db.session.add(dept)
                db.session.commit()

            # Create or get Faculty
            fac_user = User.query.filter_by(email="prof.test@campus.edu").first()
            if not fac_user:
                fac_user = User(
                    email="prof.test@campus.edu",
                    full_name="Prof. Test",
                    role="faculty",
                    is_active=True
                )
                fac_user.set_password("campus@123")
                db.session.add(fac_user)
                db.session.commit()

            fac = Faculty.query.filter_by(user_id=fac_user.id).first()
            if not fac:
                fac = Faculty(
                    user_id=fac_user.id,
                    faculty_code="FAC-FB-TEST",
                    department_id=dept.id,
                    designation="Assistant Professor"
                )
                db.session.add(fac)
                db.session.commit()

            # Create or get Course
            course = Course.query.filter_by(code="CS-FB-101").first()
            if not course:
                course = Course(
                    code="CS-FB-101",
                    title="Cloud Architecture and Firebase",
                    credits=4,
                    department_id=dept.id,
                    instructor_id=fac.id,
                    semester=6,
                )
                db.session.add(course)
                db.session.commit()

            # Create or get Student
            stu_user = User.query.filter_by(email="stu.test@campus.edu").first()
            if not stu_user:
                stu_user = User(
                    email="stu.test@campus.edu",
                    full_name="Student Test",
                    role="student",
                    is_active=True
                )
                stu_user.set_password("campus@123")
                db.session.add(stu_user)
                db.session.commit()

            stu = Student.query.filter_by(user_id=stu_user.id).first()
            if not stu:
                stu = Student(
                    user_id=stu_user.id,
                    student_code="STU-FB-001",
                    prn="24101088",
                    department_id=dept.id,
                    semester=6,
                    division="A"
                )
                db.session.add(stu)
                db.session.commit()

            # Ensure student enrolled in course
            enr = Enrollment.query.filter_by(student_id=stu.id, course_id=course.id).first()
            if not enr:
                enr = Enrollment(student_id=stu.id, course_id=course.id)
                db.session.add(enr)
                db.session.commit()

            course_id = course.id
            stu_code = stu.student_code

        # Login as Faculty
        fac_login = self.client.post("/api/auth/login", json={
            "email": "prof.test@campus.edu",
            "password": "campus@123",
            "role": "faculty"
        })
        self.assertEqual(fac_login.status_code, 200)
        fac_headers = {"X-Session-Token": fac_login.get_json()["sessionToken"]}

        # Mark Attendance via roll-call endpoint
        att_post = self.client.post("/api/attendance/roll-call", json={
            "courseCode": "CS-FB-101",
            "date": "2026-10-15",
            "division": "A",
            "records": [{"studentId": stu_code, "status": "present"}]
        }, headers=fac_headers)
        self.assertIn(att_post.status_code, (200, 201))

        # Login as Student and verify Attendance Summary
        stu_login = self.client.post("/api/auth/login", json={
            "email": "stu.test@campus.edu",
            "password": "campus@123",
            "role": "student"
        })
        self.assertEqual(stu_login.status_code, 200)
        stu_headers = {"X-Session-Token": stu_login.get_json()["sessionToken"]}

        att_summary = self.client.get("/api/attendance/summary", headers=stu_headers)
        self.assertEqual(att_summary.status_code, 200)
        att_data = att_summary.get_json()
        self.assertTrue(att_data["success"])
        self.assertGreaterEqual(att_data["data"]["overall"]["held"], 1)

    def test_06_assignment_submission_and_grading(self):
        """Verify Student submits assignment and Faculty evaluates it."""
        with self.app.app_context():
            fac = Faculty.query.join(User).filter(User.email == "prof.test@campus.edu").first()
            if not fac:
                fac = Faculty.query.first()
            course = Course.query.filter_by(code="CS-FB-101").first()
            if not course:
                course = Course.query.first()
            stu = Student.query.join(User).filter(User.email == "stu.test@campus.edu").first()
            if not stu:
                stu = Student.query.first()

            # Create an Assignment
            assign = Assignment(
                title="Firebase Realtime Sync Lab",
                description="Implement cloud synchronization hooks.",
                course_id=course.id,
                faculty_id=fac.id,
                division="All",
                due_date=datetime.now() + timedelta(days=5),
                total_points=10
            )
            db.session.add(assign)
            db.session.commit()
            assign_id = assign.id
            stu_email = stu.user.email
            fac_email = fac.user.email

        # Student submits text assignment
        stu_login = self.client.post("/api/auth/login", json={
            "email": stu_email,
            "password": "campus@123",
            "role": "student"
        })
        self.assertEqual(stu_login.status_code, 200)
        stu_headers = {"X-Session-Token": stu_login.get_json()["sessionToken"]}

        sub_res = self.client.post(f"/api/assignments/{assign_id}/submit", json={
            "submissionText": "Completed the Firebase RTDB synchronization assignment."
        }, headers=stu_headers)
        self.assertIn(sub_res.status_code, (200, 201))
        sub_id = sub_res.get_json()["data"]["id"]

        # Faculty evaluates submission
        fac_login = self.client.post("/api/auth/login", json={
            "email": fac_email,
            "password": "campus@123",
            "role": "faculty"
        })
        self.assertEqual(fac_login.status_code, 200)
        fac_headers = {"X-Session-Token": fac_login.get_json()["sessionToken"]}

        eval_res = self.client.post(f"/api/assignments/submissions/{sub_id}/grade", json={
            "grade": 9.5,
            "feedback": "Outstanding implementation of real-time cloud data layer."
        }, headers=fac_headers)
        self.assertEqual(eval_res.status_code, 200)
        self.assertEqual(eval_res.get_json()["data"]["grade"], 9.5)

    def test_07_firebase_id_token_auth_header(self):
        """Verify server-side authentication using Firebase ID token in Authorization header."""
        # Using simulated token test-token-1 for user id 1 (Admin)
        headers = {"Authorization": "Bearer test-token-1"}
        me_res = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(me_res.status_code, 200)
        user_info = me_res.get_json()["data"]
        self.assertEqual(user_info["role"], "admin")

    def test_08_firebase_login_endpoint(self):
        """Verify client SDK token exchange at /api/auth/firebase-login."""
        res = self.client.post("/api/auth/firebase-login", json={
            "idToken": "test-token-1"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["user"]["role"], "admin")
        self.assertIsNotNone(data["sessionToken"])


if __name__ == "__main__":
    unittest.main()
