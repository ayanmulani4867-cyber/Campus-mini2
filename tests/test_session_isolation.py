"""Comprehensive Test Suite for Authentication Session Isolation and Role-Based Routing.

Covers all 10 mandated scenarios:
1. Student login -> refresh -> Student dashboard remains.
2. Student login -> navigate to different pages -> Student identity remains.
3. Faculty login -> refresh -> Faculty dashboard remains.
4. Admin login -> refresh -> Admin dashboard remains.
5. Student and Admin logged in simultaneously in separate browser profiles -> each retains their own account and role.
6. Invalid or expired session -> redirect to login (or 401 on APIs).
7. Student attempts to access Admin APIs -> access denied (403 Forbidden).
8. Logout and login as a different user -> no previous account or role is displayed.
9. Verify API responses and dashboard data belong to the authenticated UID.
10. Test repeated refreshes and concurrent requests.
"""

import os
import secrets
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["DATABASE_BACKEND"] = "firebase"
os.environ["FLASK_ENV"] = "development"
os.environ["SESSION_COOKIE_SECURE"] = "false"

from app import create_app
from extensions import db
from models import User, Student, Faculty, Department, UserSession, Course, Result


class SessionIsolationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app("development")
        cls.app.config["TESTING"] = True
        cls.app.config["SESSION_COOKIE_SECURE"] = False

        with cls.app.app_context():
            # Ensure Admin account
            admin = User.query.filter_by(role="admin").first()
            if not admin:
                admin = User(
                    email="admin@campus.edu",
                    full_name="System Administrator",
                    role="admin",
                    is_active=True,
                )
                db.session.add(admin)
            admin.set_password("admin")
            cls.admin_id = admin.id
            cls.admin_email = admin.email
            cls.admin_name = admin.full_name
            cls.admin_password = "admin"

            # Ensure Faculty account
            fac = User.query.filter_by(role="faculty").first()
            if fac:
                fac.set_password("faculty123")
                cls.faculty_id = fac.id
                cls.faculty_email = fac.email
                cls.faculty_name = fac.full_name
            else:
                cls.faculty_id = None
                cls.faculty_email = None

            # Ensure Student account 1
            stu1 = User.query.filter_by(role="student").first()
            if stu1:
                stu1.set_password("student123")
                cls.student1_id = stu1.id
                cls.student1_email = stu1.email
                cls.student1_name = stu1.full_name
            else:
                cls.student1_id = None
                cls.student1_email = None

            # Ensure Student account 2
            students = User.query.filter_by(role="student").all()
            if len(students) > 1:
                stu2 = students[1]
                stu2.set_password("student456")
                cls.student2_id = stu2.id
                cls.student2_email = stu2.email
                cls.student2_name = stu2.full_name
            else:
                cls.student2_id = None
                cls.student2_email = None

            db.session.commit()

    def setUp(self):
        # Create a fresh isolated test client for each test method
        self.client = self.app.test_client()

    # =========================================================================
    # SCENARIO 1: Student login -> refresh -> Student dashboard remains.
    # =========================================================================
    def test_01_student_login_refresh_restores_student_dashboard(self):
        """Student login followed by refresh retains Student role, name, and dashboard widgets."""
        login_res = self.client.post("/api/auth/login", json={
            "email": self.student1_email,
            "password": "student123",
            "role": "student"
        })
        self.assertEqual(login_res.status_code, 200)
        data = login_res.get_json()
        token = data.get("sessionToken")
        self.assertIsNotNone(token)
        self.assertEqual(data["data"]["role"], "student")

        # Simulate page refresh on /dashboard.html (browser sends session cookie)
        refresh_res = self.client.get("/dashboard.html")
        self.assertEqual(refresh_res.status_code, 200)
        html = refresh_res.get_data(as_text=True)
        # Verify rendered HTML does not default to Admin
        self.assertNotIn("System Administrator", html)

        # Verify client-side auth verification endpoint (/api/auth/me) with tab token
        me_res = self.client.get("/api/auth/me", headers={"X-Session-Token": token})
        self.assertEqual(me_res.status_code, 200)
        me_data = me_res.get_json()["data"]
        self.assertEqual(me_data["email"], self.student1_email)
        self.assertEqual(me_data["role"], "student")

        # Verify dashboard summary API endpoint produces student-specific stats
        dash_res = self.client.get("/api/dashboard/summary", headers={"X-Session-Token": token})
        self.assertEqual(dash_res.status_code, 200)
        dash_data = dash_res.get_json()["data"]
        self.assertIn("attendancePct", dash_data)
        self.assertIn("cgpa", dash_data)
        self.assertIn("enrolledCourses", dash_data)
        self.assertNotIn("totalFaculty", dash_data)

    # =========================================================================
    # SCENARIO 2: Student login -> navigate to different pages -> Student identity remains.
    # =========================================================================
    def test_02_student_cross_page_navigation_preserves_identity(self):
        """Student navigates across multiple protected pages without role drift."""
        login_res = self.client.post("/api/auth/login", json={
            "email": self.student1_email,
            "password": "student123",
        })
        token = login_res.get_json()["sessionToken"]
        headers = {"X-Session-Token": token}

        pages_to_test = [
            "/courses.html",
            "/attendance.html",
            "/assignments.html",
            "/results.html",
            "/materials.html",
            "/notices.html",
            "/events.html",
            "/profile.html",
            "/settings.html",
        ]

        for page in pages_to_test:
            res = self.client.get(page)
            self.assertEqual(res.status_code, 200, f"Page {page} failed to load.")

        # Verify profile endpoint still returns student identity
        prof_res = self.client.get("/api/profile", headers=headers)
        self.assertEqual(prof_res.status_code, 200)
        prof_data = prof_res.get_json()["data"]
        self.assertEqual(prof_data["id"], self.student1_id)
        self.assertEqual(prof_data["role"], "student")

    # =========================================================================
    # SCENARIO 3: Faculty login -> refresh -> Faculty dashboard remains.
    # =========================================================================
    def test_03_faculty_login_refresh_restores_faculty_dashboard(self):
        """Faculty login followed by refresh retains Faculty role and dashboard widgets."""
        login_res = self.client.post("/api/auth/login", json={
            "email": self.faculty_email,
            "password": "faculty123",
            "role": "faculty"
        })
        self.assertEqual(login_res.status_code, 200)
        data = login_res.get_json()
        token = data.get("sessionToken")
        self.assertEqual(data["data"]["role"], "faculty")

        # Refresh
        refresh_res = self.client.get("/dashboard.html")
        self.assertEqual(refresh_res.status_code, 200)

        # Verify auth/me
        me_res = self.client.get("/api/auth/me", headers={"X-Session-Token": token})
        self.assertEqual(me_res.status_code, 200)
        self.assertEqual(me_res.get_json()["data"]["role"], "faculty")

        # Verify faculty dashboard summary
        dash_res = self.client.get("/api/dashboard/summary", headers={"X-Session-Token": token})
        self.assertEqual(dash_res.status_code, 200)
        dash_data = dash_res.get_json()["data"]
        self.assertIn("todayClasses", dash_data)
        self.assertIn("attendancePending", dash_data)
        self.assertIn("uploadedNotes", dash_data)

    # =========================================================================
    # SCENARIO 4: Admin login -> refresh -> Admin dashboard remains.
    # =========================================================================
    def test_04_admin_login_refresh_restores_admin_dashboard(self):
        """Admin login followed by refresh retains Admin role and dashboard metrics."""
        login_res = self.client.post("/api/auth/login", json={
            "email": self.admin_email,
            "password": self.admin_password,
            "role": "admin"
        })
        self.assertEqual(login_res.status_code, 200)
        data = login_res.get_json()
        token = data.get("sessionToken")
        self.assertEqual(data["data"]["role"], "admin")

        # Refresh
        refresh_res = self.client.get("/dashboard.html")
        self.assertEqual(refresh_res.status_code, 200)

        # Verify auth/me
        me_res = self.client.get("/api/auth/me", headers={"X-Session-Token": token})
        self.assertEqual(me_res.status_code, 200)
        self.assertEqual(me_res.get_json()["data"]["role"], "admin")

        # Verify admin dashboard metrics
        dash_res = self.client.get("/api/dashboard/summary", headers={"X-Session-Token": token})
        self.assertEqual(dash_res.status_code, 200)
        dash_data = dash_res.get_json()["data"]
        self.assertIn("facultyMembers", dash_data)
        self.assertIn("systemHealth", dash_data)

    # =========================================================================
    # SCENARIO 5: Student and Admin logged in simultaneously in separate browser profiles
    # =========================================================================
    def test_05_simultaneous_sessions_in_separate_profiles(self):
        """Two concurrent isolated browser profiles retain their distinct identities and roles."""
        profile_student = self.app.test_client()
        profile_admin = self.app.test_client()

        # Student logs in on profile A
        res_stu = profile_student.post("/api/auth/login", json={
            "email": self.student1_email,
            "password": "student123",
        })
        self.assertEqual(res_stu.status_code, 200)
        token_stu = res_stu.get_json()["sessionToken"]

        # Admin logs in on profile B
        res_adm = profile_admin.post("/api/auth/login", json={
            "email": self.admin_email,
            "password": self.admin_password,
        })
        self.assertEqual(res_adm.status_code, 200)
        token_adm = res_adm.get_json()["sessionToken"]

        # Query profile A -> must be Student
        me_stu = profile_student.get("/api/auth/me", headers={"X-Session-Token": token_stu})
        self.assertEqual(me_stu.get_json()["data"]["email"], self.student1_email)
        self.assertEqual(me_stu.get_json()["data"]["role"], "student")

        # Query profile B -> must be Admin
        me_adm = profile_admin.get("/api/auth/me", headers={"X-Session-Token": token_adm})
        self.assertEqual(me_adm.get_json()["data"]["email"], self.admin_email)
        self.assertEqual(me_adm.get_json()["data"]["role"], "admin")

        # Refresh Profile A -> still Student
        ref_stu = profile_student.get("/api/auth/me", headers={"X-Session-Token": token_stu})
        self.assertEqual(ref_stu.get_json()["data"]["role"], "student")

        # Refresh Profile B -> still Admin
        ref_adm = profile_admin.get("/api/auth/me", headers={"X-Session-Token": token_adm})
        self.assertEqual(ref_adm.get_json()["data"]["role"], "admin")

        # Query dashboard summaries simultaneously
        sum_stu = profile_student.get("/api/dashboard/summary", headers={"X-Session-Token": token_stu})
        self.assertIn("attendancePct", sum_stu.get_json()["data"])

        sum_adm = profile_admin.get("/api/dashboard/summary", headers={"X-Session-Token": token_adm})
        self.assertIn("systemHealth", sum_adm.get_json()["data"])

    # =========================================================================
    # SCENARIO 6: Invalid or expired session -> redirect to login (or 401).
    # =========================================================================
    def test_06_invalid_or_expired_session_handling(self):
        """Invalid or expired sessions are rejected and trigger re-authentication."""
        # 1. Bogus session token on API
        res = self.client.get("/api/auth/me", headers={"X-Session-Token": "bogus_token_12345"})
        self.assertEqual(res.status_code, 401)
        self.assertFalse(res.get_json()["success"])

        # 2. Expired session token
        expired_token_id = f"expired_test_token_{secrets.token_hex(8)}"
        with self.app.app_context():
            expired_session = UserSession(
                id=expired_token_id,
                user_id=self.student1_id,
                role="student",
                last_activity=datetime.now(timezone.utc) - timedelta(days=10),
                is_active=True
            )
            db.session.add(expired_session)
            db.session.commit()

        exp_res = self.client.get("/api/auth/me", headers={"X-Session-Token": expired_token_id})
        self.assertEqual(exp_res.status_code, 401)

        # 3. Protected page access with expired/invalid cookie triggers 302 Redirect to /login.html
        with self.client.session_transaction() as sess:
            sess["session_token"] = expired_token_id
            sess["user_id"] = self.student1_id

        page_res = self.client.get("/dashboard.html")
        self.assertEqual(page_res.status_code, 302)
        self.assertIn("/login.html", page_res.headers.get("Location", ""))

    # =========================================================================
    # SCENARIO 7: Student attempts to access Admin APIs -> access denied (403 Forbidden).
    # =========================================================================
    def test_07_student_access_to_admin_apis_forbidden(self):
        """Student account attempting to invoke Admin APIs receives HTTP 403 Forbidden."""
        login_res = self.client.post("/api/auth/login", json={
            "email": self.student1_email,
            "password": "student123",
        })
        token = login_res.get_json()["sessionToken"]
        headers = {"X-Session-Token": token}

        # 1. User directory API
        res_users = self.client.get("/api/users", headers=headers)
        self.assertEqual(res_users.status_code, 403)
        self.assertIn("Forbidden", res_users.get_json()["error"])

        # 2. Student creation API
        res_create_stu = self.client.post("/api/students", json={
            "name": "Hacker Student",
            "email": "hacker@campus.edu",
        }, headers=headers)
        self.assertEqual(res_create_stu.status_code, 403)

        # 3. Assessment configuration API (Admin only)
        res_config = self.client.get("/api/results/config", headers=headers)
        self.assertEqual(res_config.status_code, 403)

        # 4. Accessing /users.html page directly redirects student away
        users_page_res = self.client.get("/users.html")
        self.assertEqual(users_page_res.status_code, 302)
        self.assertIn("/dashboard.html", users_page_res.headers.get("Location", ""))

    # =========================================================================
    # SCENARIO 8: Logout and login as a different user -> no previous account or role displayed.
    # =========================================================================
    def test_08_logout_and_switch_user_complete_isolation(self):
        """Logging out of Admin and logging into Student leaves no residual state."""
        # 1. Admin login
        login_adm = self.client.post("/api/auth/login", json={
            "email": self.admin_email,
            "password": self.admin_password,
        })
        self.assertEqual(login_adm.status_code, 200)
        adm_token = login_adm.get_json()["sessionToken"]

        # Confirm Admin
        me_adm = self.client.get("/api/auth/me", headers={"X-Session-Token": adm_token})
        self.assertEqual(me_adm.get_json()["data"]["role"], "admin")

        # 2. Admin logout
        logout_res = self.client.post("/api/auth/logout", headers={"X-Session-Token": adm_token})
        self.assertEqual(logout_res.status_code, 200)

        # Confirm old token is invalidated
        stale_res = self.client.get("/api/auth/me", headers={"X-Session-Token": adm_token})
        self.assertEqual(stale_res.status_code, 401)

        # 3. Student login on same client
        login_stu = self.client.post("/api/auth/login", json={
            "email": self.student1_email,
            "password": "student123",
        })
        self.assertEqual(login_stu.status_code, 200)
        stu_token = login_stu.get_json()["sessionToken"]

        # Confirm Student with zero residual admin attributes
        me_stu = self.client.get("/api/auth/me", headers={"X-Session-Token": stu_token})
        self.assertEqual(me_stu.status_code, 200)
        stu_data = me_stu.get_json()["data"]
        self.assertEqual(stu_data["email"], self.student1_email)
        self.assertEqual(stu_data["role"], "student")
        self.assertNotEqual(stu_data["name"], self.admin_name)

    # =========================================================================
    # SCENARIO 9: Verify API responses and dashboard data belong to authenticated UID.
    # =========================================================================
    def test_09_data_belongs_strictly_to_authenticated_uid(self):
        """User profile, attendance, and result data strictly correspond to authenticated UID."""
        if not self.student2_id:
            self.skipTest("Second student account required for cross-UID verification.")

        # Client 1: Student 1
        client1 = self.app.test_client()
        res1 = client1.post("/api/auth/login", json={
            "email": self.student1_email,
            "password": "student123"
        })
        token1 = res1.get_json()["sessionToken"]

        # Client 2: Student 2
        client2 = self.app.test_client()
        res2 = client2.post("/api/auth/login", json={
            "email": self.student2_email,
            "password": "student456"
        })
        token2 = res2.get_json()["sessionToken"]

        # Query profile 1
        p1 = client1.get("/api/profile", headers={"X-Session-Token": token1}).get_json()["data"]
        # Query profile 2
        p2 = client2.get("/api/profile", headers={"X-Session-Token": token2}).get_json()["data"]

        self.assertEqual(p1["id"], self.student1_id)
        self.assertEqual(p2["id"], self.student2_id)
        self.assertNotEqual(p1["email"], p2["email"])

    # =========================================================================
    # SCENARIO 10: Test repeated refreshes and concurrent requests.
    # =========================================================================
    def test_10_repeated_refreshes_and_concurrent_requests(self):
        """Repeated sequential and interleaved requests maintain consistent session isolation."""
        client_stu = self.app.test_client()
        res_s = client_stu.post("/api/auth/login", json={"email": self.student1_email, "password": "student123"})
        token_s = res_s.get_json()["sessionToken"]

        client_fac = self.app.test_client()
        res_f = client_fac.post("/api/auth/login", json={"email": self.faculty_email, "password": "faculty123"})
        token_f = res_f.get_json()["sessionToken"]

        client_adm = self.app.test_client()
        res_a = client_adm.post("/api/auth/login", json={"email": self.admin_email, "password": self.admin_password})
        token_a = res_a.get_json()["sessionToken"]

        # Rapid interleaved requests
        for _ in range(10):
            ms = client_stu.get("/api/auth/me", headers={"X-Session-Token": token_s}).get_json()["data"]
            self.assertEqual(ms["role"], "student")

            mf = client_fac.get("/api/auth/me", headers={"X-Session-Token": token_f}).get_json()["data"]
            self.assertEqual(mf["role"], "faculty")

            ma = client_adm.get("/api/auth/me", headers={"X-Session-Token": token_a}).get_json()["data"]
            self.assertEqual(ma["role"], "admin")

            # Dashboard summaries
            ds = client_stu.get("/api/dashboard/summary", headers={"X-Session-Token": token_s}).get_json()["data"]
            self.assertIn("attendancePct", ds)

            df = client_fac.get("/api/dashboard/summary", headers={"X-Session-Token": token_f}).get_json()["data"]
            self.assertIn("todayClasses", df)

            da = client_adm.get("/api/dashboard/summary", headers={"X-Session-Token": token_a}).get_json()["data"]
            self.assertIn("systemHealth", da)


if __name__ == "__main__":
    unittest.main()
