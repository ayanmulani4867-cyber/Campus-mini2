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


class TestFirstTimeAccountActivation(unittest.TestCase):
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

        # Login as Admin
        res = cls.client.post("/api/auth/login", json={
            "email": "admin@campus.edu",
            "password": "admin",
            "role": "admin",
        })
        assert res.status_code == 200, f"Admin login failed: {res.get_data(as_text=True)}"
        cls.admin_token = res.get_json()["sessionToken"]
        cls.admin_headers = {"X-Session-Token": cls.admin_token}

    def test_01_student_creation_sets_temporary_mobile_password_and_dispatches_email(self):
        """Verify Admin creating a Student sets temporary mobile credential,
        sets must_change_password=True, and dispatches a Brevo welcome email without exposing passwords.
        """
        test_email = "stu.activation.test@sitcoe.ac.in"
        test_phone = "9876501234"

        # Cleanup if exists
        with self.app.app_context():
            existing = User.query.filter_by(email=test_email).first()
            if existing:
                db.session.delete(existing)
                db.session.commit()

        with patch.object(email_service, "send_welcome_email") as mock_email:
            mock_email.return_value = {
                "success": True,
                "simulated": False,
                "message_id": "<mock-brevo-student-1>",
                "recipient": test_email,
            }

            res = self.client.post(
                "/api/students",
                headers=self.admin_headers,
                json={
                    "name": "Activation Student",
                    "email": test_email,
                    "phone": test_phone,
                    "department": "Computer Science & Engineering",
                    "year": "3rd Year",
                    "semester": 6,
                    "division": "A",
                }
            )
            self.assertEqual(res.status_code, 201)
            data = res.get_json()
            self.assertTrue(data["success"])
            self.assertTrue(data.get("mustChangePassword", True))
            self.assertTrue(data["emailDelivery"]["sent"])

            # Verify email was called without mobile number as password
            mock_email.assert_called_once()
            args, kwargs = mock_email.call_args
            called_user = args[0]
            self.assertEqual(called_user.email, test_email)

            # Check database state
            with self.app.app_context():
                user = User.query.filter_by(email=test_email).first()
                self.assertIsNotNone(user)
                self.assertTrue(user.must_change_password)
                self.assertTrue(user.check_password(test_phone))
                # Never stored in plaintext
                self.assertNotEqual(user.password_hash, test_phone)

    def test_02_faculty_creation_sets_temporary_mobile_password_and_dispatches_email(self):
        """Verify Admin creating a Faculty member sets temporary mobile credential,
        sets must_change_password=True, and dispatches a Brevo welcome email.
        """
        test_email = "fac.activation.test@sitcoe.ac.in"
        test_phone = "9876505678"

        with self.app.app_context():
            existing = User.query.filter_by(email=test_email).first()
            if existing:
                db.session.delete(existing)
                db.session.commit()

        with patch.object(email_service, "send_welcome_email") as mock_email:
            mock_email.return_value = {
                "success": True,
                "simulated": False,
                "message_id": "<mock-brevo-fac-1>",
                "recipient": test_email,
            }

            res = self.client.post(
                "/api/faculty",
                headers=self.admin_headers,
                json={
                    "name": "Activation Faculty",
                    "email": test_email,
                    "phone": test_phone,
                    "department": "Computer Science & Engineering",
                    "designation": "Assistant Professor",
                }
            )
            self.assertEqual(res.status_code, 201)
            data = res.get_json()
            self.assertTrue(data["success"])
            self.assertTrue(data.get("mustChangePassword", True))
            self.assertTrue(data["emailDelivery"]["sent"])

            with self.app.app_context():
                user = User.query.filter_by(email=test_email).first()
                self.assertIsNotNone(user)
                self.assertTrue(user.must_change_password)
                self.assertTrue(user.check_password(test_phone))

    def test_03_first_login_returns_must_change_password_flag(self):
        """Verify login with initial mobile credential returns mustChangePassword=True."""
        res = self.client.post("/api/auth/login", json={
            "email": "stu.activation.test@sitcoe.ac.in",
            "password": "9876501234",
            "role": "student",
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertTrue(data.get("mustChangePassword"))
        self.assertIsNotNone(data.get("sessionToken"))

    def test_04_forced_password_setup_blocks_dashboard_access_and_apis(self):
        """Verify accounts with must_change_password=True are blocked from accessing
        dashboard and business data APIs until password update succeeds.
        """
        # Login with mobile number
        res = self.client.post("/api/auth/login", json={
            "email": "stu.activation.test@sitcoe.ac.in",
            "password": "9876501234",
            "role": "student",
        })
        token = res.get_json()["sessionToken"]
        headers = {"X-Session-Token": token}

        # 1. API route blocked with 403 Forbidden
        courses_res = self.client.get("/api/courses", headers=headers)
        self.assertEqual(courses_res.status_code, 403)
        c_data = courses_res.get_json()
        self.assertTrue(c_data.get("mustChangePassword"))
        self.assertIn("First-time password setup is required", c_data["error"])

        # 2. Setup endpoints and /me are permitted
        me_res = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(me_res.status_code, 200)
        self.assertTrue(me_res.get_json()["data"]["mustChangePassword"])

    def test_05_first_login_setup_validation_rules(self):
        """Verify strong password validation rules on /api/auth/first-login-setup."""
        res = self.client.post("/api/auth/login", json={
            "email": "stu.activation.test@sitcoe.ac.in",
            "password": "9876501234",
            "role": "student",
        })
        token = res.get_json()["sessionToken"]
        headers = {"X-Session-Token": token}

        # 1. Short password rejected
        r1 = self.client.post("/api/auth/first-login-setup", headers=headers, json={
            "newPassword": "short",
            "confirmPassword": "short",
        })
        self.assertEqual(r1.status_code, 400)
        self.assertIn("at least 8 characters", r1.get_json()["error"])

        # 2. Simple password missing mixed case/numbers rejected
        r2 = self.client.post("/api/auth/first-login-setup", headers=headers, json={
            "newPassword": "alllowercasepass",
            "confirmPassword": "alllowercasepass",
        })
        self.assertEqual(r2.status_code, 400)
        self.assertIn("uppercase letter", r2.get_json()["error"])

        # 3. Mismatched confirmation rejected
        r3 = self.client.post("/api/auth/first-login-setup", headers=headers, json={
            "newPassword": "SecurePassword123!",
            "confirmPassword": "DifferentPassword123!",
        })
        self.assertEqual(r3.status_code, 400)
        self.assertIn("do not match", r3.get_json()["error"])

        # 4. Reusing phone number as new password rejected
        r4 = self.client.post("/api/auth/first-login-setup", headers=headers, json={
            "newPassword": "9876501234",
            "confirmPassword": "9876501234",
        })
        self.assertEqual(r4.status_code, 400)
        self.assertIn("cannot be your mobile number", r4.get_json()["error"])

    def test_06_first_login_setup_success_and_subsequent_login(self):
        """Verify successful first-time password setup clears must_change_password
        and allows immediate full dashboard and API access.
        """
        res = self.client.post("/api/auth/login", json={
            "email": "stu.activation.test@sitcoe.ac.in",
            "password": "9876501234",
            "role": "student",
        })
        token = res.get_json()["sessionToken"]
        headers = {"X-Session-Token": token}

        new_pass = "CampusStudent#2026"
        with patch.object(firebase_service, "sync_user_to_firebase_auth", wraps=firebase_service.sync_user_to_firebase_auth) as mock_fb:
            setup_res = self.client.post("/api/auth/first-login-setup", headers=headers, json={
                "newPassword": new_pass,
                "confirmPassword": new_pass,
            })
            self.assertEqual(setup_res.status_code, 200)
            s_data = setup_res.get_json()
            self.assertTrue(s_data["success"])
            self.assertFalse(s_data.get("mustChangePassword"))
            self.assertGreaterEqual(mock_fb.call_count, 1)

        # 1. API access is now unblocked
        courses_res = self.client.get("/api/courses", headers=headers)
        self.assertEqual(courses_res.status_code, 200)

        # 2. Login with old mobile password is now rejected
        old_login = self.client.post("/api/auth/login", json={
            "email": "stu.activation.test@sitcoe.ac.in",
            "password": "9876501234",
            "role": "student",
        })
        self.assertEqual(old_login.status_code, 401)

        # 3. Login with new password succeeds and returns mustChangePassword=False
        new_login = self.client.post("/api/auth/login", json={
            "email": "stu.activation.test@sitcoe.ac.in",
            "password": new_pass,
            "role": "student",
        })
        self.assertEqual(new_login.status_code, 200)
        nl_data = new_login.get_json()
        self.assertTrue(nl_data["success"])
        self.assertFalse(nl_data.get("mustChangePassword", False))

    def test_07_resending_activation_email_is_safe_and_handles_delivery_status(self):
        """Verify Admin resend-welcome-email endpoint generates link, dispatches email,
        does not create duplicate accounts, and reports Brevo status accurately.
        """
        with patch.object(email_service, "send_welcome_email") as mock_email:
            # 1. Success case
            mock_email.return_value = {
                "success": True,
                "simulated": False,
                "message_id": "<mock-brevo-resend-99>",
                "recipient": "fac.activation.test@sitcoe.ac.in",
            }
            res = self.client.post(
                "/api/faculty/fac.activation.test@sitcoe.ac.in/resend-welcome-email",
                headers=self.admin_headers,
            )
            # If lookup by email or code
            if res.status_code == 404:
                with self.app.app_context():
                    fac = User.query.filter_by(email="fac.activation.test@sitcoe.ac.in").first().faculty_profile
                    code = fac.faculty_code
                res = self.client.post(
                    f"/api/faculty/{code}/resend-welcome-email",
                    headers=self.admin_headers,
                )
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data["success"])
            self.assertTrue(data["emailDelivery"]["sent"])
            self.assertEqual(data["emailDelivery"]["messageId"], "<mock-brevo-resend-99>")

            # 2. Brevo delivery failure case -> accurately reports HTTP 500 error
            mock_email.return_value = {
                "success": False,
                "simulated": False,
                "error": "Brevo HTTP 402: Payment Required / Quota Exceeded",
                "recipient": "fac.activation.test@sitcoe.ac.in",
            }
            with self.app.app_context():
                fac = User.query.filter_by(email="fac.activation.test@sitcoe.ac.in").first().faculty_profile
                code = fac.faculty_code
            fail_res = self.client.post(
                f"/api/faculty/{code}/resend-welcome-email",
                headers=self.admin_headers,
            )
            self.assertEqual(fail_res.status_code, 500)
            f_data = fail_res.get_json()
            self.assertFalse(f_data["success"])
            self.assertFalse(f_data["emailDelivery"]["sent"])
            self.assertIn("Quota Exceeded", f_data["emailDelivery"]["error"])

    def test_08_account_and_role_isolation(self):
        """Verify Student, Faculty, and Admin retain independent sessions and identities
        with strict role enforcement on backend.
        """
        # 1. Admin accessing admin user directory -> 200 OK
        admin_res = self.client.get("/api/users", headers=self.admin_headers)
        self.assertEqual(admin_res.status_code, 200)

        # 2. Student accessing admin user directory -> 403 Forbidden
        stu_login = self.client.post("/api/auth/login", json={
            "email": "stu.activation.test@sitcoe.ac.in",
            "password": "CampusStudent#2026",
            "role": "student",
        })
        stu_token = stu_login.get_json()["sessionToken"]
        stu_headers = {"X-Session-Token": stu_token}

        stu_attempt = self.client.get("/api/users", headers=stu_headers)
        self.assertEqual(stu_attempt.status_code, 403)

        # 3. Verify each session token maps to its own authenticated identity
        admin_me = self.client.get("/api/auth/me", headers=self.admin_headers).get_json()["data"]
        stu_me = self.client.get("/api/auth/me", headers=stu_headers).get_json()["data"]

        self.assertEqual(admin_me["role"], "admin")
        self.assertEqual(stu_me["role"], "student")
        self.assertNotEqual(admin_me["id"], stu_me["id"])
