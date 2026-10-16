import os
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["DATABASE_BACKEND"] = "firebase"
os.environ["FLASK_ENV"] = "development"

from app import create_app
from extensions import db
from models import User, Faculty, FacultyAssignment, Course, Department
from services.email_service import email_service
from services.firebase_service import firebase_service


class TestFacultySubjectAssignment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

        with cls.app.app_context():
            # Ensure Admin exists
            cls.admin = User.query.filter_by(role="admin").first()
            if not cls.admin:
                cls.admin = User(
                    email="admin@campus.edu",
                    full_name="System Administrator",
                    role="admin",
                    is_active=True,
                )
                cls.admin.set_password("admin")
                db.session.add(cls.admin)
                db.session.commit()

            # Ensure Department exists
            cls.dept = Department.resolve("Computer Science & Engineering")
            if not cls.dept:
                cls.dept = Department(name="Computer Science & Engineering", code="CSE")
                db.session.add(cls.dept)
                db.session.commit()

            # Ensure at least 3 courses exist for testing
            cls.course1 = Course.query.filter_by(code="SUBJ-TEST-101").first()
            if not cls.course1:
                cls.course1 = Course(
                    code="SUBJ-TEST-101",
                    title="Database Systems Testing",
                    department_id=cls.dept.id,
                    semester=3,
                    credits=4,
                    status="active"
                )
                db.session.add(cls.course1)

            cls.course2 = Course.query.filter_by(code="SUBJ-TEST-102").first()
            if not cls.course2:
                cls.course2 = Course(
                    code="SUBJ-TEST-102",
                    title="Computer Networks Testing",
                    department_id=cls.dept.id,
                    semester=4,
                    credits=4,
                    status="active"
                )
                db.session.add(cls.course2)

            cls.course3 = Course.query.filter_by(code="SUBJ-TEST-103").first()
            if not cls.course3:
                cls.course3 = Course(
                    code="SUBJ-TEST-103",
                    title="Operating Systems Testing",
                    department_id=cls.dept.id,
                    semester=5,
                    credits=3,
                    status="active"
                )
                db.session.add(cls.course3)

            db.session.commit()

        # Login as Admin
        admin_login = cls.client.post("/api/auth/login", json={
            "email": "admin@campus.edu",
            "password": "admin",
            "role": "admin",
        })
        cls.admin_token = admin_login.get_json()["sessionToken"]
        cls.admin_headers = {"X-Session-Token": cls.admin_token}

    def test_01_dynamic_subjects_available_from_database(self):
        """Verify available subjects/courses are dynamically loaded from database."""
        res = self.client.get("/api/courses", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        courses = data.get("data", [])
        self.assertGreaterEqual(len(courses), 3)

        codes = [c.get("code") for c in courses]
        self.assertIn("SUBJ-TEST-101", codes)
        self.assertIn("SUBJ-TEST-102", codes)
        self.assertIn("SUBJ-TEST-103", codes)

        # Verify details: code, title, department, semester
        c1 = next(c for c in courses if c.get("code") == "SUBJ-TEST-101")
        self.assertEqual(c1["title"], "Database Systems Testing")
        self.assertEqual(c1["semester"], 3)
        self.assertIsNotNone(c1.get("id"))

    def test_02_add_faculty_with_multiple_selected_subjects(self):
        """Verify Admin can create a faculty member with multiple selected subjects."""
        test_email = "fac.multisubject@sitcoe.ac.in"
        test_phone = "9876543201"

        with self.app.app_context():
            old = User.query.filter_by(email=test_email).first()
            if old:
                db.session.delete(old)
                db.session.commit()

        with patch.object(email_service, "send_welcome_email") as mock_email:
            mock_email.return_value = {
                "success": True,
                "simulated": False,
                "message_id": "<mock-brevo-multi-1>",
                "recipient": test_email,
            }

            payload = {
                "name": "Prof. Multi Subject",
                "email": test_email,
                "phone": test_phone,
                "department": "Computer Science & Engineering",
                "designation": "Associate Professor",
                "assignments": [
                    {
                        "courseCode": "SUBJ-TEST-101",
                        "subject": "Database Systems Testing",
                        "year": "2nd Year",
                        "semester": 3,
                        "divisions": ["A", "B"]
                    },
                    {
                        "courseCode": "SUBJ-TEST-102",
                        "subject": "Computer Networks Testing",
                        "year": "2nd Year",
                        "semester": 4,
                        "divisions": ["A"]
                    }
                ]
            }

            res = self.client.post("/api/faculty", headers=self.admin_headers, json=payload)
            self.assertEqual(res.status_code, 201)
            f_data = res.get_json()["data"]
            self.assertEqual(f_data["name"], "Prof. Multi Subject")
            self.assertIn("Database Systems Testing", f_data["assignedSubjects"])
            self.assertIn("Computer Networks Testing", f_data["assignedSubjects"])
            self.assertEqual(len(f_data["assignedSubjects"]), 2)

            # Check database records
            with self.app.app_context():
                user = User.query.filter_by(email=test_email).first()
                self.assertIsNotNone(user)
                fac = user.faculty_profile
                self.assertIsNotNone(fac)
                self.assertEqual(len(fac.assignments), 3) # Div A and B for course 1, Div A for course 2
                assigned_courses = {a.course.code for a in fac.assignments}
                self.assertEqual(assigned_courses, {"SUBJ-TEST-101", "SUBJ-TEST-102"})

    def test_03_prevent_duplicate_and_invalid_subject_assignments(self):
        """Verify validation prevents invalid courses and handles duplicate entries."""
        # 1. Invalid course reference
        res = self.client.post("/api/faculty", headers=self.admin_headers, json={
            "name": "Prof. Invalid Course",
            "email": "fac.invalid@sitcoe.ac.in",
            "phone": "9876543202",
            "department": "Computer Science & Engineering",
            "designation": "Assistant Professor",
            "assignments": [
                {
                    "courseCode": "NON-EXISTENT-9999",
                    "subject": "Ghost Course",
                    "divisions": ["A"]
                }
            ]
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("was not found", res.get_json().get("error", ""))

        # 2. Duplicate entries in payload are deduplicated
        test_email = "fac.dedup@sitcoe.ac.in"
        with self.app.app_context():
            old = User.query.filter_by(email=test_email).first()
            if old:
                db.session.delete(old)
                db.session.commit()

        with patch.object(email_service, "send_welcome_email") as mock_email:
            mock_email.return_value = {"success": True, "message_id": "<m1>"}
            dup_res = self.client.post("/api/faculty", headers=self.admin_headers, json={
                "name": "Prof. Dedup Test",
                "email": test_email,
                "phone": "9876543203",
                "department": "Computer Science & Engineering",
                "designation": "Assistant Professor",
                "assignments": [
                    { "courseCode": "SUBJ-TEST-101", "divisions": ["A"] },
                    { "courseCode": "SUBJ-TEST-101", "divisions": ["A"] } # duplicate!
                ]
            })
            self.assertEqual(dup_res.status_code, 201)
            data = dup_res.get_json()["data"]
            self.assertEqual(len(data["assignedSubjects"]), 1)

    def test_04_edit_faculty_member_assignments(self):
        """Verify Admin can edit a faculty member's assignments (remove subject, add new subject)."""
        # Fetch existing faculty member
        user_res = self.client.get("/api/faculty", headers=self.admin_headers)
        facs = user_res.get_json()["data"]
        target = next((f for f in facs if f["email"] == "fac.multisubject@sitcoe.ac.in"), None)
        self.assertIsNotNone(target)
        fac_code = target["facultyCode"]

        # Update: remove SUBJ-TEST-101, keep SUBJ-TEST-102, add SUBJ-TEST-103
        update_res = self.client.put(f"/api/faculty/{fac_code}", headers=self.admin_headers, json={
            "name": "Prof. Multi Subject Updated",
            "phone": "9876543201",
            "department": "Computer Science & Engineering",
            "designation": "Professor",
            "assignments": [
                {
                    "courseCode": "SUBJ-TEST-102",
                    "subject": "Computer Networks Testing",
                    "year": "2nd Year",
                    "semester": 4,
                    "divisions": ["A", "B"]
                },
                {
                    "courseCode": "SUBJ-TEST-103",
                    "subject": "Operating Systems Testing",
                    "year": "3rd Year",
                    "semester": 5,
                    "divisions": ["A"]
                }
            ]
        })
        self.assertEqual(update_res.status_code, 200)
        u_data = update_res.get_json()["data"]
        self.assertEqual(u_data["name"], "Prof. Multi Subject Updated")
        self.assertNotIn("Database Systems Testing", u_data["assignedSubjects"])
        self.assertIn("Computer Networks Testing", u_data["assignedSubjects"])
        self.assertIn("Operating Systems Testing", u_data["assignedSubjects"])
        self.assertEqual(len(u_data["assignedSubjects"]), 2)

    def test_05_persistence_after_refresh_or_rehydration(self):
        """Verify assignments persist accurately when re-queried from database."""
        get_res = self.client.get("/api/faculty", headers=self.admin_headers)
        self.assertEqual(get_res.status_code, 200)
        facs = get_res.get_json()["data"]
        target = next((f for f in facs if f["email"] == "fac.multisubject@sitcoe.ac.in"), None)
        self.assertIsNotNone(target)

        self.assertEqual(target["designation"], "Professor")
        self.assertIn("Computer Networks Testing", target["assignedSubjects"])
        self.assertIn("Operating Systems Testing", target["assignedSubjects"])
        self.assertNotIn("Database Systems Testing", target["assignedSubjects"])

    def test_06_faculty_login_only_sees_assigned_subjects(self):
        """Verify that when the faculty member logs in, they only see their assigned subjects."""
        # Authenticate as faculty
        fac_login = self.client.post("/api/auth/login", json={
            "email": "fac.multisubject@sitcoe.ac.in",
            "password": "9876543201",
            "role": "faculty",
        })
        self.assertEqual(fac_login.status_code, 200)
        fac_token = fac_login.get_json()["sessionToken"]
        fac_headers = {"X-Session-Token": fac_token}

        # First complete first-login setup if flagged
        if fac_login.get_json().get("mustChangePassword"):
            with patch.object(firebase_service, "sync_user_to_firebase_auth", wraps=firebase_service.sync_user_to_firebase_auth):
                self.client.post("/api/auth/first-login-setup", headers=fac_headers, json={
                    "newPassword": "ProfSubject#2026",
                    "confirmPassword": "ProfSubject#2026",
                })

        # 1. Fetch courses as faculty -> MUST return only assigned courses (SUBJ-TEST-102 and SUBJ-TEST-103)
        courses_res = self.client.get("/api/courses", headers=fac_headers)
        self.assertEqual(courses_res.status_code, 200)
        my_courses = courses_res.get_json().get("data", [])
        my_codes = [c["code"] for c in my_courses]

        self.assertIn("SUBJ-TEST-102", my_codes)
        self.assertIn("SUBJ-TEST-103", my_codes)
        # SUBJ-TEST-101 was removed during edit, so it MUST NOT appear!
        self.assertNotIn("SUBJ-TEST-101", my_codes)

        # 2. Check dashboard summary
        dash_res = self.client.get("/api/dashboard/summary", headers=fac_headers)
        self.assertEqual(dash_res.status_code, 200)
        dash_data = dash_res.get_json().get("data", {})
        self.assertEqual(dash_data.get("todayClasses"), 2)


if __name__ == "__main__":
    unittest.main()
