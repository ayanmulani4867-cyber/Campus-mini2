import io
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from datetime import datetime, timezone, timedelta
from app import create_app
from extensions import db
from models import (
    User, Student, Faculty, Department, Course, Enrollment, FacultyAssignment,
    Result, AssessmentConfig, Assignment, AssignmentSubmission, AuditLog, log_audit
)


class TestCompleteUpgrade(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def login_as(self, email, password):
        return self.client.post(
            "/api/auth/login",
            data=json.dumps({"email": email, "password": password}),
            content_type="application/json"
        )

    def logout(self):
        return self.client.post("/api/auth/logout")

    def test_complete_upgrade_suite(self):
        """End-to-end automated verification of the 12-Module Master Upgrade."""
        with self.app.app_context():
            # Ensure SITCOE department exists
            cse_dept = Department.query.filter_by(code="CSE").first()
            if not cse_dept:
                cse_dept = Department(name="Computer Science & Engineering", code="CSE")
                db.session.add(cse_dept)
                db.session.commit()

            # Ensure course exists
            test_course = Course.query.filter_by(code="CS601").first()
            if not test_course:
                test_course = Course(
                    code="CS601",
                    title="Software Engineering & Cloud Computing",
                    credits=4,
                    department_id=cse_dept.id,
                    semester=6
                )
                db.session.add(test_course)
                db.session.commit()

            # Setup or get Admin
            admin_user = User.query.filter_by(email="admin@campus.edu").first()
            if not admin_user:
                admin_user = User(email="admin@campus.edu", full_name="Campus Admin", role="admin")
                db.session.add(admin_user)
            admin_user.set_password("admin")
            db.session.commit()

            # Setup test faculty
            fac_user = User.query.filter_by(email="prof.test@sitcoe.ac.in").first()
            if not fac_user:
                fac_user = User(email="prof.test@sitcoe.ac.in", full_name="Prof. Test Faculty", role="faculty")
                fac_user.set_password("faculty123")
                db.session.add(fac_user)
                db.session.flush()

                fac_prof = Faculty(
                    user_id=fac_user.id,
                    faculty_code="FAC-TEST-01",
                    designation="Assistant Professor",
                    department_id=cse_dept.id
                )
                db.session.add(fac_prof)
                db.session.flush()
            else:
                fac_prof = fac_user.faculty_profile

                # Assign to CS601 Div A
            assign = FacultyAssignment.query.filter_by(
                faculty_id=fac_prof.id,
                course_id=test_course.id,
                semester=6,
                division="A"
            ).first()
            if not assign:
                assign = FacultyAssignment(
                    faculty_id=fac_prof.id,
                    course_id=test_course.id,
                    division="A",
                    semester=6,
                    year_label="TY B.Tech"
                )
                db.session.add(assign)
                db.session.commit()

            # Setup test student
            stu_user = User.query.filter_by(email="student.test@sitcoe.ac.in").first()
            if not stu_user:
                stu_user = User(email="student.test@sitcoe.ac.in", full_name="Aarav Sharma", role="student")
                stu_user.set_password("student123")
                db.session.add(stu_user)
                db.session.flush()

                stu_prof = Student(
                    user_id=stu_user.id,
                    student_code="STU-TEST-01",
                    prn="24101099",
                    roll_number="42",
                    department_id=cse_dept.id,
                    semester=6,
                    division="A",
                    year_label="TY B.Tech"
                )
                db.session.add(stu_prof)
                db.session.flush()
            else:
                stu_prof = stu_user.student_profile

            enr = Enrollment.query.filter_by(student_id=stu_prof.id, course_id=test_course.id).first()
            if not enr:
                enr = Enrollment(student_id=stu_prof.id, course_id=test_course.id)
                db.session.add(enr)
                db.session.commit()

            # Clean up prior test result & test assignment to ensure idempotency
            old_res = Result.query.filter_by(student_id=stu_prof.id, course_id=test_course.id).first()
            if old_res:
                db.session.delete(old_res)
            old_asgns = Assignment.query.filter_by(course_id=test_course.id, title="Module 8 Lab Assignment on Concurrency").all()
            for oa in old_asgns:
                AssignmentSubmission.query.filter_by(assignment_id=oa.id).delete()
                db.session.delete(oa)
            db.session.commit()

        # =========================================================================
        # MODULE 1: ADMIN USER DIRECTORY SEARCH & FILTERING
        # =========================================================================
        res = self.login_as("admin@campus.edu", "admin")
        self.assertEqual(res.status_code, 200, res.data)

        # 1.1 Search by name
        res = self.client.get("/api/users?q=Aarav")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()["data"]
        self.assertTrue(any("Aarav" in u["name"] for u in data))

        # 1.2 Search by PRN
        res = self.client.get("/api/users?q=24101099")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()["data"]
        self.assertGreaterEqual(len(data), 1)
        self.assertEqual(data[0]["prn"], "24101099")

        # 1.3 Role filter (students)
        res = self.client.get("/api/users?role=student")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()["data"]
        self.assertTrue(all(u["role"] == "student" for u in data))

        # 1.4 Role filter (faculty)
        res = self.client.get("/api/users?role=faculty")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()["data"]
        self.assertTrue(all(u["role"] == "faculty" for u in data))

        # 1.5 Department and semester combined filter
        res = self.client.get("/api/users?department=CSE&semester=6&division=A")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()["data"]
        self.assertTrue(any(u["name"] == "Aarav Sharma" for u in data))

        # 1.6 Pagination & sorting
        res = self.client.get("/api/users?page=1&limit=5&sort_by=name&sort_order=asc")
        self.assertEqual(res.status_code, 200)
        json_data = res.get_json()
        self.assertIn("pagination", json_data)
        self.assertEqual(json_data["pagination"]["page"], 1)
        self.assertIn("stats", json_data)
        self.logout()

        # =========================================================================
        # MODULE 2: COMPLETE FACULTY MARKS ENTRY (CA1, CA2, Mid-Sem, End-Sem)
        # =========================================================================
        # Login as assigned faculty
        res = self.login_as("prof.test@sitcoe.ac.in", "faculty123")
        self.assertEqual(res.status_code, 200)

        # 2.1 Invalid marks out-of-bounds rejection (CA1 max is 20, sending 25)
        bad_payload = {
            "studentId": "24101099",
            "courseCode": "CS601",
            "ca1Marks": 25.0,  # Invalid: > 20
            "action": "save_draft"
        }
        res_bad = self.client.post("/api/results/marks", data=json.dumps(bad_payload), content_type="application/json")
        self.assertIn(res_bad.status_code, (400, 422), f"Expected validation failure for marks > 20, got {res_bad.status_code}")

        # 2.2 Valid 4-assessment draft marks entry
        valid_payload = {
            "studentId": "24101099",
            "courseCode": "CS601",
            "ca1Marks": 18.0,
            "ca2Marks": 19.0,
            "midSemMarks": 26.0,
            "endSemMarks": 62.0,
            "attendanceStatus": "present",
            "action": "save_draft"
        }
        res_valid = self.client.post("/api/results/marks", data=json.dumps(valid_payload), content_type="application/json")
        self.assertEqual(res_valid.status_code, 200, res_valid.data)
        res_data = res_valid.get_json()["data"]
        self.assertEqual(res_data["ca1"], 18.0)
        self.assertEqual(res_data["ca2"], 19.0)
        self.assertEqual(res_data["midSem"], 26.0)
        self.assertEqual(res_data["endSem"], 62.0)
        self.assertEqual(res_data["status"], "draft")

        # 2.3 Submit marks for review (locks normal draft modification)
        submit_payload = {
            "studentId": "24101099",
            "courseCode": "CS601",
            "action": "submit"
        }
        res_sub = self.client.post("/api/results/marks", data=json.dumps(submit_payload), content_type="application/json")
        self.assertEqual(res_sub.status_code, 200)
        self.assertEqual(res_sub.get_json()["data"]["status"], "submitted")

        self.logout()

        # 2.4 Unauthorized faculty access attempt (should be rejected with 403)
        with self.app.app_context():
            dept = Department.query.filter_by(code="CSE").first()
            unauth_fac = User.query.filter_by(email="unauth.fac@sitcoe.ac.in").first()
            if not unauth_fac:
                unauth_fac = User(email="unauth.fac@sitcoe.ac.in", full_name="Prof. Other Faculty", role="faculty")
                unauth_fac.set_password("faculty123")
                db.session.add(unauth_fac)
                db.session.flush()
                fac_p = Faculty(user_id=unauth_fac.id, faculty_code="FAC-UNAUTH", department_id=dept.id)
                db.session.add(fac_p)
                db.session.commit()

        self.login_as("unauth.fac@sitcoe.ac.in", "faculty123")
        res_forbidden = self.client.post("/api/results/marks", data=json.dumps(valid_payload), content_type="application/json")
        self.assertEqual(res_forbidden.status_code, 403, f"Expected 403 for unassigned faculty, got {res_forbidden.status_code}")
        self.logout()

        # =========================================================================
        # MODULE 3: RESULT CONTROL AND PUBLISHING LIFECYCLE
        # =========================================================================
        # Student cannot view unpublished results
        self.login_as("student.test@sitcoe.ac.in", "student123")
        res_stu_results = self.client.get("/api/results")
        self.assertEqual(res_stu_results.status_code, 200)
        self.assertEqual(len(res_stu_results.get_json()["data"]), 0, "Student must NOT see unpublished results!")
        self.logout()

        # Admin reviews and approves batch
        self.login_as("admin@campus.edu", "admin")

        # Under Review
        res_rev = self.client.post("/api/results/batch-status", data=json.dumps({
            "courseCode": "CS601",
            "division": "A",
            "status": "under_review"
        }), content_type="application/json")
        self.assertEqual(res_rev.status_code, 200)

        # Approved
        res_app = self.client.post("/api/results/batch-status", data=json.dumps({
            "courseCode": "CS601",
            "division": "A",
            "status": "approved"
        }), content_type="application/json")
        self.assertEqual(res_app.status_code, 200)

        # Published
        res_pub = self.client.post("/api/results/batch-status", data=json.dumps({
            "courseCode": "CS601",
            "division": "A",
            "status": "published"
        }), content_type="application/json")
        self.assertEqual(res_pub.status_code, 200)

        # Reopening without reason must fail (HTTP 400)
        res_reopen_fail = self.client.post("/api/results/batch-status", data=json.dumps({
            "courseCode": "CS601",
            "division": "A",
            "status": "reopened",
            "reason": ""  # Missing mandatory reason
        }), content_type="application/json")
        self.assertIn(res_reopen_fail.status_code, (400, 422))

        # Reopening with reason succeeds and creates audit log
        res_reopen_ok = self.client.post("/api/results/batch-status", data=json.dumps({
            "courseCode": "CS601",
            "division": "A",
            "status": "reopened",
            "reason": "Authorized re-evaluation after grievance review."
        }), content_type="application/json")
        self.assertEqual(res_reopen_ok.status_code, 200)

        # Re-publish for modules 4, 5, 6
        self.client.post("/api/results/batch-status", data=json.dumps({
            "courseCode": "CS601",
            "division": "A",
            "status": "published"
        }), content_type="application/json")

        # =========================================================================
        # MODULE 4: ADMIN STUDENT RESULT CARD
        # =========================================================================
        res_card = self.client.get("/api/results/card/24101099")
        self.assertEqual(res_card.status_code, 200, res_card.data)
        card_data = res_card.get_json()["data"]
        self.assertEqual(card_data["student"]["name"], "Aarav Sharma")
        self.assertEqual(card_data["student"]["prn"], "24101099")
        self.assertIn("institution", card_data)
        self.assertIn("SITCOE", card_data["institution"]["shortName"])
        self.assertGreaterEqual(len(card_data["subjects"]), 1)
        self.assertGreater(card_data["summary"]["percentage"], 0)
        self.assertIn(card_data["summary"]["grade"], ("A+", "A", "B+", "B", "C", "D"))

        # =========================================================================
        # MODULE 5: TOPPERS AND MERIT LIST
        # =========================================================================
        res_toppers = self.client.get("/api/results/toppers?department=CSE&semester=6&limit=10")
        self.assertEqual(res_toppers.status_code, 200, res_toppers.data)
        toppers_data = res_toppers.get_json()["data"]
        self.assertGreaterEqual(len(toppers_data), 1)
        self.assertEqual(toppers_data[0]["rank"], 1)
        self.assertEqual(toppers_data[0]["prn"], "24101099")
        self.assertEqual(toppers_data[0]["status"], "PASSED")

        # =========================================================================
        # MODULE 6: RESULT ANALYTICS AND PASS PERCENTAGE
        # =========================================================================
        res_ana = self.client.get("/api/results/analytics?department=CSE&semester=6")
        self.assertEqual(res_ana.status_code, 200, res_ana.data)
        ana_data = res_ana.get_json()["data"]
        self.assertGreaterEqual(ana_data["publishedCount"], 1)
        self.assertGreaterEqual(ana_data["passedCount"], 1)
        self.assertEqual(ana_data["passPercentage"], 100.0)
        self.assertIn("gradeDistribution", ana_data)

        # =========================================================================
        # MODULE 7: STUDENT PERFORMANCE HISTORY
        # =========================================================================
        res_hist = self.client.get("/api/results/history/24101099")
        self.assertEqual(res_hist.status_code, 200, res_hist.data)
        hist_data = res_hist.get_json()["data"]
        self.assertGreaterEqual(len(hist_data), 1)
        self.assertIn("Semester 6", hist_data[0]["semester"])
        self.assertEqual(hist_data[0]["backlogs"], 0)

        # =========================================================================
        # MODULE 8: ASSIGNMENT MANAGEMENT WITH SUBMISSION LOCK
        # =========================================================================
        # Admin or faculty creates assignment
        asgn_payload = {
            "title": "Module 8 Lab Assignment on Concurrency",
            "courseCode": "CS601",
            "division": "A",
            "dueDate": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "totalPoints": 10,
            "description": "Implement robust thread-safe transaction pool."
        }
        res_asgn = self.client.post("/api/assignments", data=json.dumps(asgn_payload), content_type="application/json")
        self.assertIn(res_asgn.status_code, (200, 201), res_asgn.data)
        asgn_id = res_asgn.get_json()["data"]["id"]
        self.logout()

        # Student submits assignment
        self.login_as("student.test@sitcoe.ac.in", "student123")
        sub_payload = {"submissionText": "Official Student Submission Text v1"}
        res_sub_1 = self.client.post(f"/api/assignments/{asgn_id}/submit", data=json.dumps(sub_payload), content_type="application/json")
        self.assertIn(res_sub_1.status_code, (200, 201), res_sub_1.data)
        self.assertTrue(res_sub_1.get_json()["isLocked"])
        sub_id = res_sub_1.get_json()["data"]["id"]

        # Student attempts to resubmit or modify locked submission (MUST BE REJECTED WITH 403)
        res_sub_2 = self.client.post(f"/api/assignments/{asgn_id}/submit", data=json.dumps({
            "submissionText": "Tampered modification attempt"
        }), content_type="application/json")
        self.assertEqual(res_sub_2.status_code, 403, f"Expected 403 for locked submission, got {res_sub_2.status_code}")
        self.assertIn("disabled", res_sub_2.get_json()["error"].lower())
        self.logout()

        # Admin exceptionally unlocks submission
        self.login_as("admin@campus.edu", "admin")
        res_unlock = self.client.post(f"/api/assignments/{asgn_id}/submissions/{sub_id}/unlock", data=json.dumps({
            "reason": "Approved medical emergency exception."
        }), content_type="application/json")
        self.assertEqual(res_unlock.status_code, 200, res_unlock.data)
        self.assertFalse(res_unlock.get_json()["data"]["isLocked"])
        self.logout()

        # Student can now submit correction and it immediately re-locks
        self.login_as("student.test@sitcoe.ac.in", "student123")
        res_sub_3 = self.client.post(f"/api/assignments/{asgn_id}/submit", data=json.dumps({
            "submissionText": "Corrected and finalized submission v2"
        }), content_type="application/json")
        self.assertEqual(res_sub_3.status_code, 200, res_sub_3.data)
        self.assertTrue(res_sub_3.get_json()["isLocked"])

        # Further edits are locked again
        res_sub_4 = self.client.post(f"/api/assignments/{asgn_id}/submit", data=json.dumps({
            "submissionText": "Second modification attempt"
        }), content_type="application/json")
        self.assertEqual(res_sub_4.status_code, 403)
        self.logout()

        # =========================================================================
        # MODULE 10: AUDIT LOGGING VERIFICATION
        # =========================================================================
        self.login_as("admin@campus.edu", "admin")
        res_audit = self.client.get("/api/audit?limit=50")
        self.assertEqual(res_audit.status_code, 200, res_audit.data)
        audit_entries = res_audit.get_json()["data"]
        actions = [a["action"] for a in audit_entries]
        self.assertTrue(any("MARKS" in act for act in actions), "Expected MARKS audit entry")
        self.assertTrue(any("ASSIGNMENT" in act for act in actions), "Expected ASSIGNMENT audit entry")
        self.assertTrue(any("RESULT_LIFECYCLE" in act for act in actions), "Expected RESULT_LIFECYCLE audit entry")
        self.logout()


if __name__ == "__main__":
    unittest.main()
