import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["DATABASE_BACKEND"] = "firebase"
os.environ["FLASK_ENV"] = "development"

from app import create_app
from extensions import db
from models import User, Student, Faculty, Department, UserSession
from services.email_service import email_service
from services.firebase_service import firebase_service


class TestBrevoEmailAndAuth(unittest.TestCase):
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
            cls.dept = Department.query.first()
            if not cls.dept:
                cls.dept = Department(name="Computer Science & Engineering", code="CSE")
                db.session.add(cls.dept)
                db.session.commit()

        # Login as Admin to get session token
        res = cls.client.post("/api/auth/login", json={
            "email": "admin@campus.edu",
            "password": "admin",
            "role": "admin",
        })
        assert res.status_code == 200, f"Admin login failed: {res.get_data(as_text=True)}"
        cls.admin_token = res.get_json()["sessionToken"]
        cls.admin_headers = {"X-Session-Token": cls.admin_token}

    def test_01_email_template_rendering(self):
        """Verify HTML email template does not expose plain-text passwords and contains setup link."""
        with self.app.app_context():
            user = User(email="template.test@sitcoe.ac.in", full_name="Template Tester", role="student")
            student = Student(student_code="STU999", prn="24101099", year_label="3rd Year", division="A")

            fake_link = "https://campus-mini2.firebaseapp.com/__/auth/action?mode=resetPassword&apiKey=AIzaFakeKey"
            html = email_service._render_welcome_html(
                name=user.full_name,
                role_label="Student",
                email=user.email,
                details=[("Student PRN", "24101099"), ("Division", "A")],
                setup_link=fake_link,
                login_url="http://localhost:5000/login.html",
                sender_name="Campus Connect ERP",
            )

            # Security checks
            self.assertIn(fake_link, html)
            self.assertIn("Template Tester", html)
            self.assertIn("24101099", html)
            self.assertIn("Set Up Your Password", html)
            self.assertIn("Security Notice", html)
            self.assertNotIn("password_hash", html)
            self.assertNotIn("pbkdf2", html)

    def test_02_brevo_api_call_success_and_failure(self):
        """Verify Brevo API caller parses 201 Created and handles API failure codes gracefully."""
        with self.app.app_context():
            user = User(email="brevo.mock@sitcoe.ac.in", full_name="Brevo Mock", role="faculty")

            # 1. Test successful Brevo delivery
            with patch("requests.post") as mock_post:
                mock_res = MagicMock()
                mock_res.status_code = 201
                mock_res.content = b'{"messageId": "<mock-brevo-msg-id-123>"}'
                mock_res.json.return_value = {"messageId": "<mock-brevo-msg-id-123>"}
                mock_post.return_value = mock_res

                with patch.dict(os.environ, {"BREVO_API_KEY": "xkeysib-mock-valid-api-key"}):
                    res = email_service.send_welcome_email(user, None, "https://fake.link")
                    self.assertTrue(res["success"])
                    self.assertEqual(res["message_id"], "<mock-brevo-msg-id-123>")
                    self.assertFalse(res["simulated"])

            # 2. Test Brevo API failure (e.g. invalid sender or auth error)
            with patch("requests.post") as mock_post:
                mock_res = MagicMock()
                mock_res.status_code = 401
                mock_res.text = "Key not found in account"
                mock_post.return_value = mock_res

                with patch.dict(os.environ, {"BREVO_API_KEY": "xkeysib-invalid-api-key"}):
                    res = email_service.send_welcome_email(user, None, "https://fake.link")
                    self.assertFalse(res["success"])
                    self.assertIn("Brevo HTTP 401", res["error"])

    def test_03_firebase_password_reset_link_generation(self):
        """Verify Firebase Admin SDK generates a valid action URL."""
        with self.app.app_context():
            admin_user = User.query.filter_by(role="admin").first()
            link = firebase_service.generate_password_reset_link(admin_user.email)
            self.assertIsNotNone(link)
            self.assertIn("resetPassword", link)
            self.assertTrue(link.startswith("http"))

    def test_04_dual_mode_password_authentication(self):
        """Verify login succeeds via local hash or fallback Firebase Auth verification."""
        with self.app.app_context():
            test_user = User.query.filter_by(email="auth.dual@sitcoe.ac.in").first()
            if not test_user:
                test_user = User(
                    email="auth.dual@sitcoe.ac.in",
                    full_name="Dual Auth Tester",
                    role="student",
                    is_active=True,
                )
                db.session.add(test_user)
            test_user.set_password("initial_secure_local_pass")
            db.session.commit()

        # 1. Login with local hash works
        res1 = self.client.post("/api/auth/login", json={
            "email": "auth.dual@sitcoe.ac.in",
            "password": "initial_secure_local_pass",
            "role": "student",
        })
        self.assertEqual(res1.status_code, 200)

        # 2. Login with wrong password rejected
        res2 = self.client.post("/api/auth/login", json={
            "email": "auth.dual@sitcoe.ac.in",
            "password": "totally_wrong_password",
            "role": "student",
        })
        self.assertEqual(res2.status_code, 401)

        # 3. User set new password in Firebase Auth (simulating reset link completed)
        # Mock verify_password_with_firebase returning True for the newly set password
        with patch.object(firebase_service, "verify_password_with_firebase", return_value=True):
            res3 = self.client.post("/api/auth/login", json={
                "email": "auth.dual@sitcoe.ac.in",
                "password": "new_password_from_firebase_link_123",
                "role": "student",
            })
            self.assertEqual(res3.status_code, 200)
            self.assertIsNotNone(res3.get_json()["sessionToken"])

        # 4. Now the local hash has been automatically synchronized!
        # The user can log in with the new password without hitting Firebase Auth REST API again!
        with patch.object(firebase_service, "verify_password_with_firebase", return_value=False):
            res4 = self.client.post("/api/auth/login", json={
                "email": "auth.dual@sitcoe.ac.in",
                "password": "new_password_from_firebase_link_123",
                "role": "student",
            })
            self.assertEqual(res4.status_code, 200)

    def test_05_admin_create_student_triggers_welcome_email(self):
        """Verify student creation triggers Brevo email dispatch with setup link and no plain-text password."""
        email = "new.student.welcome@sitcoe.ac.in"
        # Clean up if existed from previous run
        with self.app.app_context():
            old = User.query.filter_by(email=email).first()
            if old:
                db.session.delete(old)
                db.session.commit()

        res = self.client.post("/api/students", json={
            "name": "Welcome Student Test",
            "email": email,
            "department": "CSE",
            "phone": "9876543210",
            "year": "2nd Year",
            "semester": 4,
            "division": "B",
        }, headers=self.admin_headers)

        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("emailDelivery", data)
        self.assertEqual(data["emailDelivery"]["recipient"], email)
        self.assertTrue(data["emailDelivery"]["sent"])

        # Verify password in database is NOT 9876543210 or campus@123
        with self.app.app_context():
            created_user = User.query.filter_by(email=email).first()
            self.assertIsNotNone(created_user)
            self.assertFalse(created_user.check_password("9876543210"))
            self.assertFalse(created_user.check_password("campus@123"))

        # 6. Idempotent Retry: Re-submitting the same student resends the email without failing on duplicate
        retry_res = self.client.post("/api/students", json={
            "name": "Welcome Student Test",
            "email": email,
            "department": "CSE",
            "phone": "9876543210",
        }, headers=self.admin_headers)
        self.assertEqual(retry_res.status_code, 200)
        self.assertIn("Resent welcome email", retry_res.get_json()["message"])

        # 7. Dedicated Resend Endpoint
        code = data["data"]["studentCode"]
        resend_res = self.client.post(f"/api/students/{code}/resend-welcome-email", headers=self.admin_headers)
        self.assertEqual(resend_res.status_code, 200)
        self.assertTrue(resend_res.get_json()["success"])

    def test_06_admin_create_faculty_triggers_welcome_email(self):
        """Verify faculty creation triggers Brevo email dispatch with setup link and handles resend."""
        email = "new.faculty.welcome@sitcoe.ac.in"
        with self.app.app_context():
            old = User.query.filter_by(email=email).first()
            if old:
                db.session.delete(old)
                db.session.commit()

        res = self.client.post("/api/faculty", json={
            "name": "Prof. Welcome Test",
            "email": email,
            "department": "CSE",
            "phone": "9812345678",
            "designation": "Associate Professor",
        }, headers=self.admin_headers)

        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("emailDelivery", data)
        self.assertEqual(data["emailDelivery"]["recipient"], email)

        # Idempotent retry test
        retry_res = self.client.post("/api/faculty", json={
            "name": "Prof. Welcome Test",
            "email": email,
            "department": "CSE",
            "phone": "9812345678",
        }, headers=self.admin_headers)
        self.assertEqual(retry_res.status_code, 200)
        self.assertIn("Resent welcome email", retry_res.get_json()["message"])

        # Dedicated Resend Endpoint on Faculty
        code = data["data"]["facultyCode"]
        resend_res = self.client.post(f"/api/faculty/{code}/resend-welcome-email", headers=self.admin_headers)
        self.assertEqual(resend_res.status_code, 200)

        # Resend via User ID endpoint
        uid = data["data"]["userId"]
        user_resend_res = self.client.post(f"/api/users/{uid}/resend-welcome-email", headers=self.admin_headers)
        self.assertEqual(user_resend_res.status_code, 200)


if __name__ == "__main__":
    unittest.main()
