"""Comprehensive Automated Test Suite for Master Prompt Bug Fixes:
1. Automatic Logout elimination & session persistence
2. Student attendance retrieval, calculations & DOM persistence
3. All four assessments (CA1, CA2, Mid-Sem, End-Sem)
4. Result cards, toppers & examination analytics
5. Assignment submission locking enforcement & audit logging
6. Role-based access control and data security
"""

import unittest
from datetime import datetime, timezone, timedelta
from app import create_app
from extensions import db
from models import (
    User, Student, Faculty, Course, Department, Enrollment,
    AttendanceSession, AttendanceRecord, Result, AssessmentConfig,
    Assignment, AssignmentSubmission, UserSession, AuditLog
)
from utils.auth import SESSION_MAX_AGE_HOURS


class MasterPromptFixesTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app("development")
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

    # =========================================================================
    # MODULE 1: FIX AUTOMATIC LOGOUT & SESSION MANAGEMENT
    # =========================================================================
    def test_01_proxyfix_and_session_config(self):
        """Verify ProxyFix middleware, persistent session lifetime, and teardown cleanup."""
        # 1. Verify ProxyFix is in wsgi_app chain
        self.assertTrue(
            hasattr(self.app.wsgi_app, "orig_wsgi_app") or "ProxyFix" in type(self.app.wsgi_app).__name__,
            "ProxyFix middleware should wrap wsgi_app for reverse proxy deployments (Render)."
        )

        # 2. Verify Session settings
        self.assertEqual(self.app.config.get("SESSION_COOKIE_NAME"), "campus_session")
        self.assertTrue(self.app.config.get("SESSION_COOKIE_HTTPONLY"))
        self.assertEqual(self.app.config.get("SESSION_COOKIE_SAMESITE"), "Lax")
        self.assertGreaterEqual(self.app.config.get("PERMANENT_SESSION_LIFETIME"), timedelta(days=7))
        self.assertGreaterEqual(SESSION_MAX_AGE_HOURS, 24 * 7)

    def test_02_session_token_and_cookie_auth(self):
        """Verify tab session token and cookie authentication persist across requests."""
        with self.app.app_context():
            admin = User.query.filter_by(role="admin").first()
            self.assertIsNotNone(admin)

            # Test login
            res = self.client.post("/api/auth/login", json={
                "email": admin.email,
                "password": "admin"
            })
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            token = data.get("sessionToken")
            self.assertIsNotNone(token)

            # Verify /api/auth/me with X-Session-Token
            me_res = self.client.get("/api/auth/me", headers={"X-Session-Token": token})
            self.assertEqual(me_res.status_code, 200)
            self.assertEqual(me_res.get_json()["data"]["email"], admin.email)

            # Verify /api/auth/me with Cookie session
            cookie_res = self.client.get("/api/auth/me")
            self.assertEqual(cookie_res.status_code, 200)
            self.assertEqual(cookie_res.get_json()["data"]["email"], admin.email)

    def test_03_html_page_navigation_does_not_redirect(self):
        """Verify protected page GET routes load the HTML shell without premature 302 redirect."""
        # When accessing without a cookie, the HTML template shell should render (HTTP 200)
        # so client-side JavaScript can present the tab session token without being booted
        res = self.client.get("/attendance.html")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"studentAttendanceSection", res.data)
        self.assertIn(b"facultyRollCallCard", res.data)

        dash_res = self.client.get("/dashboard.html")
        self.assertEqual(res.status_code, 200)

    # =========================================================================
    # MODULE 3: FIX STUDENT ATTENDANCE
    # =========================================================================
    def test_04_student_attendance_summary_and_history(self):
        """Verify student attendance retrieves real DB records, percentages, and history."""
        with self.app.app_context():
            student = Student.query.first()
            self.assertIsNotNone(student)
            user = student.user
            self.assertIsNotNone(user)

            # Log in as student
            res = self.client.post("/api/auth/login", json={
                "email": user.email,
                "password": "student123"
            })
            if res.status_code != 200:
                # If password different, authenticate via session
                with self.client.session_transaction() as sess:
                    sess["user_id"] = user.id
                    sess["role"] = user.role
            else:
                token = res.get_json().get("sessionToken")
                headers = {"X-Session-Token": token}

            att_res = self.client.get("/api/attendance/summary")
            self.assertEqual(att_res.status_code, 200)
            data = att_res.get_json()
            self.assertTrue(data.get("success"))
            self.assertIn("data", data)
            att_data = data["data"]

            self.assertIn("rows", att_data)
            self.assertIn("history", att_data)
            self.assertIn("overall", att_data)

            overall = att_data["overall"]
            self.assertIn("percentage", overall)
            self.assertIn("held", overall)
            self.assertIn("attended", overall)
            self.assertIn("presentCount", overall)
            self.assertIn("absentCount", overall)
            self.assertIn("lateCount", overall)

            # Verification: student cannot access another student's attendance by passing studentId
            other_res = self.client.get("/api/attendance/summary?studentId=STU-FAKE-999")
            self.assertEqual(other_res.status_code, 200)
            # The returned data should still be for the authenticated student, not the fake one
            self.assertEqual(other_res.get_json()["data"]["overall"]["held"], overall["held"])

    # =========================================================================
    # MODULE 6: VERIFY ALL FOUR ASSESSMENTS (CA1, CA2, Mid-Sem, End-Sem)
    # =========================================================================
    def test_05_all_four_assessments_schema_and_workflow(self):
        """Verify CA1, CA2, Mid-Sem, End-Sem attributes, max marks, and status lifecycle."""
        with self.app.app_context():
            cfg = AssessmentConfig.query.first()
            if not cfg:
                from routes.results import _get_or_create_config
                cfg = _get_or_create_config()

            self.assertEqual(cfg.ca1_max, 20.0)
            self.assertEqual(cfg.ca2_max, 20.0)
            self.assertEqual(cfg.mid_sem_max, 30.0)
            self.assertEqual(cfg.end_sem_max, 70.0)

            # Test result model fields
            res = Result.query.first()
            if res:
                self.assertIsNotNone(res.ca1_max)
                self.assertIsNotNone(res.ca2_max)
                self.assertIsNotNone(res.mid_sem_max)
                self.assertIsNotNone(res.end_sem_max)
                self.assertIn(res.status, ["draft", "submitted", "under_review", "approved", "published", "reopened"])

    # =========================================================================
    # MODULE 7: RESULT CARDS, TOPPERS AND ANALYTICS
    # =========================================================================
    def test_06_result_card_and_analytics_endpoints(self):
        """Verify student result card lookup by PRN/Code/ID and examination analytics."""
        with self.app.app_context():
            student = Student.query.first()
            self.assertIsNotNone(student)

            # Authenticate as admin
            admin = User.query.filter_by(role="admin").first()
            with self.client.session_transaction() as sess:
                sess["user_id"] = admin.id
                sess["role"] = admin.role

            # 1. Lookup result card by PRN or Student Code
            card_res = self.client.get(f"/api/results/card/{student.prn or student.student_code}")
            self.assertEqual(card_res.status_code, 200)
            card_data = card_res.get_json()
            self.assertTrue(card_data["success"])
            self.assertIn("student", card_data["data"])
            self.assertIn("summary", card_data["data"])
            self.assertIn("subjects", card_data["data"])

            # 2. Examination Analytics
            analytics_res = self.client.get("/api/results/analytics")
            self.assertEqual(analytics_res.status_code, 200)
            analytics_data = analytics_res.get_json()
            self.assertTrue(analytics_data["success"])
            self.assertIn("passPercentage", analytics_data["data"])
            self.assertIn("gradeDistribution", analytics_data["data"])

            # 3. Toppers List
            toppers_res = self.client.get("/api/results/toppers")
            self.assertEqual(toppers_res.status_code, 200)
            self.assertTrue(toppers_res.get_json()["success"])

    # =========================================================================
    # MODULE 8: ASSIGNMENT SUBMISSION LOCKING & AUDIT
    # =========================================================================
    def test_07_assignment_submission_locking(self):
        """Verify assignments lock after submission and reject subsequent edit attempts."""
        with self.app.app_context():
            student = Student.query.first()
            self.assertIsNotNone(student)
            assignment = Assignment.query.first()

            if assignment:
                # Find or check submission
                sub = AssignmentSubmission.query.filter_by(
                    assignment_id=assignment.id, student_id=student.id
                ).first()
                if not sub:
                    sub = AssignmentSubmission(
                        assignment_id=assignment.id,
                        student_id=student.id,
                        submission_text="Initial submission",
                        is_locked=True
                    )
                    db.session.add(sub)
                    db.session.commit()

                self.assertTrue(sub.is_locked)

                # Attempt resubmission as student
                with self.client.session_transaction() as sess:
                    sess["user_id"] = student.user_id
                    sess["role"] = "student"

                resubmit_res = self.client.post(
                    f"/api/assignments/{assignment.id}/submit",
                    json={"submissionText": "Malicious re-submission attempt"}
                )
                # Must be rejected with HTTP 403 Forbidden
                self.assertEqual(resubmit_res.status_code, 403)
                data = resubmit_res.get_json()
                self.assertFalse(data["success"])
                self.assertTrue(data.get("isLocked"))

    # =========================================================================
    # MODULE 4 & 9: VERIFY EMPTY STATES (ZERO MOCK DATA FLASH)
    # =========================================================================
    def test_08_empty_states_and_zero_mock_records(self):
        """Verify notices and events endpoints return valid DB records with no fake fixtures."""
        with self.app.app_context():
            # Notices endpoint
            notice_res = self.client.get("/api/notices")
            self.assertEqual(notice_res.status_code, 200)
            notices_data = notice_res.get_json().get("data", [])
            # Must not contain synthetic mock titles
            mock_titles = [
                "Campus Placement Drive 2026",
                "Annual Technical Symposium - TechFest 2026",
                "Library Book Return Notice"
            ]
            for n in notices_data:
                self.assertNotIn(n.get("title"), mock_titles)

            # Events endpoint
            event_res = self.client.get("/api/events")
            self.assertEqual(event_res.status_code, 200)
            events_data = event_res.get_json().get("data", [])
            mock_event_titles = [
                "Hackathon 2026: Code for Good",
                "Annual Sports Meet 2026"
            ]
            for ev in events_data:
                self.assertNotIn(ev.get("title"), mock_event_titles)


if __name__ == "__main__":
    unittest.main()
