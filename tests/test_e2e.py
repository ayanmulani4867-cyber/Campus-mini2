import io
import sys
import os

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path

# Ensure project root is on python path
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from app import create_app
from extensions import db
from models import User, Student, Faculty, FacultyAssignment, Course, Notice, StudyMaterial, AttendanceRecord, Result

app = create_app()

def run_tests():
    print("=== STARTING COMPREHENSIVE CAMPUS CONNECT E2E VERIFICATION ===")
    client = app.test_client()

    with app.app_context():
        # 1. Test Seeded Accounts login
        print("\n--- 1. Testing Existing Seeded Accounts ---")
        for email, role in [("admin@campus.edu", "admin"), ("anita.sen@campus.edu", "faculty"), ("rahul@campus.edu", "student")]:
            resp = client.post("/api/auth/login", json={"email": email, "password": "campus@123", "role": role})
            assert resp.status_code == 200, f"Failed to login seeded {email}: {resp.get_json()}"
            print(f"✓ Seeded {role} ({email}) logged in successfully.")
            client.post("/api/auth/logout")

        # 2. Login as Admin
        print("\n--- 2. Admin Login ---")
        admin_login = client.post("/api/auth/login", json={"email": "admin@campus.edu", "password": "campus@123", "role": "admin"})
        assert admin_login.status_code == 200
        print("✓ Admin logged in.")

        # Clean up any previous test records if existed
        old_test_student = User.query.filter_by(email="rahul.test@campus.edu").first()
        if old_test_student:
            stu = Student.query.filter_by(user_id=old_test_student.id).first()
            if stu:
                from models import Enrollment, AttendanceRecord, Result
                Enrollment.query.filter_by(student_id=stu.id).delete()
                AttendanceRecord.query.filter_by(student_id=stu.id).delete()
                Result.query.filter_by(student_id=stu.id).delete()
                db.session.delete(stu)
            db.session.delete(old_test_student)
        old_test_fac = User.query.filter_by(email="anita.test@campus.edu").first()
        if old_test_fac:
            from models import AttendanceSession, StudyMaterial
            StudyMaterial.query.filter_by(uploaded_by_id=old_test_fac.id).delete()
            fac = Faculty.query.filter_by(user_id=old_test_fac.id).first()
            if fac:
                sessions = AttendanceSession.query.filter_by(marked_by_id=fac.id).all()
                for sess in sessions:
                    AttendanceRecord.query.filter_by(session_id=sess.id).delete()
                    db.session.delete(sess)
                db.session.delete(fac)
            db.session.delete(old_test_fac)
        db.session.commit()

        # 3. Admin Add Student with complete class information
        print("\n--- 3. Admin Adding Student with Complete Class Assignment ---")
        student_payload = {
            "name": "Rahul Test Sharma",
            "email": "rahul.test@campus.edu",
            "phone": "9876543299",
            "department": "Computer Science & Engineering",
            "year": "3rd Year",
            "semester": 5,
            "division": "A",
            "prn": "STU2026999"
        }
        res_stu = client.post("/api/students", json=student_payload)
        assert res_stu.status_code == 201, f"Failed adding student: {res_stu.get_json()}"
        stu_data = res_stu.get_json()["data"]
        assert stu_data["name"] == "Rahul Test Sharma"
        assert stu_data["year"] == "3rd Year"
        assert stu_data["semester"] == 5
        assert stu_data["division"] == "A"
        assert stu_data["prn"] == "STU2026999"
        print(f"✓ Student added: {stu_data['name']} (PRN: {stu_data['prn']}, Dept: {stu_data['dept']}, Class: {stu_data['year']} Sem {stu_data['semester']} Div {stu_data['division']})")

        # 4. Admin Add Faculty with multi-subject & multi-division teaching assignments
        print("\n--- 4. Admin Adding Faculty with Multi-Subject & Multi-Division Assignments ---")
        faculty_payload = {
            "name": "Anita Test Sen",
            "email": "anita.test@campus.edu",
            "phone": "9876543288",
            "department": "Computer Science & Engineering",
            "designation": "Associate Professor",
            "facultyId": "FAC2026999",
            "assignments": [
                {
                    "subject": "Database Management Systems",
                    "year": "3rd Year",
                    "semester": 5,
                    "divisions": ["A", "B"]
                },
                {
                    "subject": "Computer Networks",
                    "year": "3rd Year",
                    "semester": 5,
                    "divisions": ["A"]
                }
            ]
        }
        res_fac = client.post("/api/faculty", json=faculty_payload)
        assert res_fac.status_code == 201, f"Failed adding faculty: {res_fac.get_json()}"
        fac_data = res_fac.get_json()["data"]
        assert fac_data["name"] == "Anita Test Sen"
        assert fac_data["designation"] == "Associate Professor"
        assert any("Database" in s or "DBMS" in s for s in fac_data["assignedSubjects"])
        assert any("Computer Networks" in s for s in fac_data["assignedSubjects"])
        assert "A" in fac_data["assignedDivisions"]
        assert "B" in fac_data["assignedDivisions"]
        assert len(fac_data["assignments"]) == 3  # (DBMS, A), (DBMS, B), (CN, A)
        print(f"✓ Faculty added with 3 relational assignments: {fac_data['name']}, Subjects: {fac_data['assignedSubjects']}, Divs: {fac_data['assignedDivisions']}")

        # Verify relational database structure for faculty assignments
        rel_assignments = FacultyAssignment.query.filter_by(faculty_id=Faculty.query.filter_by(faculty_code="FAC2026999").first().id).all()
        assert len(rel_assignments) == 3, "Relational table entries count mismatch"
        for a in rel_assignments:
            print(f"  → Relational row: course_id={a.course_id} ({a.course.title if a.course else '-'}), year={a.year_label}, sem={a.semester}, div={a.division}")
        print("✓ Verified FacultyAssignment relational storage (proper normalization, NOT comma-separated string!).")

        client.post("/api/auth/logout")

        # 5. Student Login with Phone Number as Initial Password
        print("\n--- 5. Student Login with Phone Number as Initial Password ---")
        stu_login = client.post("/api/auth/login", json={"email": "rahul.test@campus.edu", "password": "9876543299", "role": "student"})
        assert stu_login.status_code == 200, f"Student initial login failed: {stu_login.get_json()}"
        me_resp = client.get("/api/auth/me")
        me_data = me_resp.get_json()["data"]
        assert me_data["role"] == "student"
        assert me_data["phone"] == "9876543299"
        assert me_data["year"] == "3rd Year"
        assert me_data["division"] == "A"
        print(f"✓ Student authenticated using phone number password. Role: {me_data['role']}, Public ID: {me_data['publicId']}")

        # 6. Student Content Filtering: Dashboard, Courses, Notices
        print("\n--- 6. Student Dashboard & Content Filtering ---")
        dash_resp = client.get("/api/dashboard/summary")
        dash_data = dash_resp.get_json()["data"]
        assert "cohort" in dash_data
        print(f"✓ Student Dashboard Cohort Badge: '{dash_data['cohort']['badge']}'")

        courses_resp = client.get("/api/courses")
        courses_data = courses_resp.get_json()["data"]
        print(f"✓ Student Enrolled Courses count: {len(courses_data)}")
        for c in courses_data:
            print(f"  → Scoped Course: {c['code']} - {c['title']} (Sem {c['semester']})")
        course_codes = [c["code"] for c in courses_data]
        assert "CS601" in course_codes or "CS602" in course_codes, "Student should have scoped courses!"

        notices_resp = client.get("/api/notices")
        notices_data = notices_resp.get_json()["data"]
        print(f"✓ Scoped Notices for student: {len(notices_data)} visible")

        client.post("/api/auth/logout")

        # 7. Faculty Login with Phone Number as Initial Password
        print("\n--- 7. Faculty Login with Phone Number as Initial Password ---")
        fac_login = client.post("/api/auth/login", json={"email": "anita.test@campus.edu", "password": "9876543288", "role": "faculty"})
        assert fac_login.status_code == 200, f"Faculty initial login failed: {fac_login.get_json()}"
        fac_me = client.get("/api/auth/me").get_json()["data"]
        assert fac_me["role"] == "faculty"
        print(f"✓ Faculty authenticated using phone number password. Designation: {fac_me['designation']}")

        # 8. Faculty Content Filtering: Courses & Roll-Call Roster
        print("\n--- 8. Faculty Courses & Roll-Call Roster Filtering ---")
        fac_courses = client.get("/api/courses").get_json()["data"]
        print(f"✓ Faculty Assigned Courses count: {len(fac_courses)}")
        for fc in fac_courses:
            print(f"  → Assigned Course: {fc['code']} - {fc['title']} (Divisions: {fc.get('assignedDivisions')})")

        # Test Roll-call roster for CS601 Div A (should contain Rahul Test Sharma)
        roster_resp = client.get("/api/attendance/roll-call?courseCode=CS601&division=A")
        assert roster_resp.status_code == 200
        roster = roster_resp.get_json()["data"]["roster"]
        rahul_in_roster = [s for s in roster if s["name"] == "Rahul Test Sharma"]
        assert len(rahul_in_roster) == 1, "Rahul should be in CS601 Division A roster!"
        print(f"✓ Verified Roll-call roster filters correctly by course and division. Found: {rahul_in_roster[0]['name']} (PRN: {rahul_in_roster[0]['prn']}, Div: {rahul_in_roster[0]['division']})")

        # Faculty Marks Attendance
        mark_att_resp = client.post("/api/attendance/roll-call", json={
            "courseCode": "CS601",
            "division": "A",
            "records": [{"studentId": rahul_in_roster[0]["studentId"], "status": "present"}]
        })
        assert mark_att_resp.status_code == 200
        print("✓ Faculty marked attendance for Rahul in Division A.")

        # Faculty Enters Marks
        mark_res_resp = client.post("/api/results", json={
            "studentId": rahul_in_roster[0]["studentId"],
            "courseCode": "CS601",
            "marks": 92
        })
        assert mark_res_resp.status_code in (200, 201), f"Marks post failed: {mark_res_resp.get_json()}"
        print(f"✓ Faculty entered marks: {mark_res_resp.get_json()['data']}")

        # 9. Faculty Uploads Study Material (PDF) associated with Dept, Year, Sem, Div, Subject
        print("\n--- 9. Study Material Upload (PDF/PPT/PPTX) with Cohort Scoping ---")
        dummy_pdf_content = b"%PDF-1.4 Mock DBMS Unit 3 Lecture Notes Content"
        upload_resp = client.post(
            "/api/materials",
            data={
                "title": "DBMS Unit 3 Transactions and Concurrency",
                "category": "Lecture Notes",
                "courseCode": "CS601",
                "division": "A",
                "file": (io.BytesIO(dummy_pdf_content), "DBMS_Unit3_Transactions.pdf")
            },
            content_type="multipart/form-data"
        )
        assert upload_resp.status_code == 201, f"Material upload failed: {upload_resp.get_json()}"
        mat_id = upload_resp.get_json()["data"]["id"]
        print(f"✓ Study material uploaded successfully: ID={mat_id}, Title='DBMS Unit 3 Transactions and Concurrency', Division=A")

        client.post("/api/auth/logout")

        # 10. Student Downloads Uploaded Study Material
        print("\n--- 10. Student Accessing Scoped Study Material ---")
        client.post("/api/auth/login", json={"email": "rahul.test@campus.edu", "password": "9876543299", "role": "student"})
        stu_materials = client.get("/api/materials").get_json()["data"]
        mat_found = [m for m in stu_materials if m["id"] == mat_id]
        assert len(mat_found) == 1, "Rahul (Div A) should see the uploaded Div A material!"
        print(f"✓ Rahul (Div A) sees material: {mat_found[0]['title']} (Division: {mat_found[0]['division']})")

        dl_resp = client.get(f"/api/materials/{mat_id}/download")
        if dl_resp.status_code != 200:
            print(f"Download returned {dl_resp.status_code}: {dl_resp.data.decode('utf-8', errors='ignore')}")
        assert dl_resp.status_code == 200
        assert dl_resp.data == dummy_pdf_content
        print("✓ Rahul downloaded study material PDF successfully.")

        client.post("/api/auth/logout")

        # 11. Admin User Directory: View Profiles & Edit Members
        print("\n--- 11. Admin User Directory View Profile & Edit ---")
        client.post("/api/auth/login", json={"email": "admin@campus.edu", "password": "campus@123", "role": "admin"})

        # View Student Profile
        view_stu = client.get(f"/api/students/STU2026999")
        assert view_stu.status_code == 200
        stu_p = view_stu.get_json()["data"]
        assert stu_p["name"] == "Rahul Test Sharma"
        assert stu_p["year"] == "3rd Year"
        assert stu_p["division"] == "A"
        print("✓ Admin User Directory → View Student Profile:")
        for k in ["name", "email", "phone", "dept", "year", "semester", "division", "prn", "status"]:
            print(f"    {k}: {stu_p.get(k)}")

        # View Faculty Profile
        view_fac = client.get(f"/api/faculty/FAC2026999")
        assert view_fac.status_code == 200
        fac_p = view_fac.get_json()["data"]
        assert fac_p["name"] == "Anita Test Sen"
        assert fac_p["designation"] == "Associate Professor"
        assert len(fac_p["assignments"]) == 3
        print("✓ Admin User Directory → View Faculty Profile:")
        for k in ["name", "email", "phone", "dept", "designation", "assignedSubjects", "assignedYears", "assignedSemesters", "assignedDivisions", "status"]:
            print(f"    {k}: {fac_p.get(k)}")

        # Edit Student Profile
        edit_stu = client.put("/api/students/STU2026999", json={
            "division": "B"
        })
        assert edit_stu.status_code == 200
        assert edit_stu.get_json()["data"]["division"] == "B"
        print("✓ Admin User Directory → Edit Student (updated Division to B)")

        # Edit Faculty Profile
        edit_fac = client.put("/api/faculty/FAC2026999", json={
            "designation": "Professor"
        })
        assert edit_fac.status_code == 200
        assert edit_fac.get_json()["data"]["designation"] == "Professor"
        # 12. Student Applies for Leave & Admin Approves Leave
        print("\n--- 12. Leave Management: Application, Review & Approval ---")
        client.post("/api/auth/login", json={"email": "rahul.test@campus.edu", "password": "9876543299", "role": "student"})
        leave_payload = {
            "leaveType": "Medical",
            "startDate": "2026-10-01",
            "endDate": "2026-10-03",
            "reason": "Viral fever and doctor-advised rest."
        }
        res_leave = client.post("/api/leaves", json=leave_payload)
        assert res_leave.status_code == 201, f"Apply leave failed: {res_leave.get_json()}"
        leave_id = res_leave.get_json()["data"]["id"]
        assert res_leave.get_json()["data"]["status"] == "pending"
        print(f"✓ Student applied for Medical Leave: ID={leave_id}, Status=pending")

        # Student checks leave status
        stu_leaves = client.get("/api/leaves").get_json()["data"]
        assert any(l["id"] == leave_id and l["status"] == "pending" for l in stu_leaves)
        print("✓ Student verified leave request in their personal list.")
        client.post("/api/auth/logout")

        # Admin reviews and approves leave
        client.post("/api/auth/login", json={"email": "admin@campus.edu", "password": "campus@123", "role": "admin"})
        approve_res = client.put(f"/api/leaves/{leave_id}/status", json={
            "status": "approved",
            "remarks": "Medical certificate verified. Approved."
        })
        assert approve_res.status_code == 200, f"Approve leave failed: {approve_res.get_json()}"
        assert approve_res.get_json()["data"]["status"] == "approved"
        print(f"✓ Admin approved leave ID={leave_id} with remarks.")
        client.post("/api/auth/logout")

        # 13. Coursework Assignments: Creation, Scoped Visibility, Submission & Grading
        print("\n--- 13. Coursework Assignments: Creation, Submission & Grading ---")
        # Faculty creates assignment
        client.post("/api/auth/login", json={"email": "anita.test@campus.edu", "password": "9876543288", "role": "faculty"})
        assign_payload = {
            "title": "Assignment 1: Relational Schema Normalization",
            "description": "Design 3NF schemas for an enterprise hospital database.",
            "courseCode": "CS601",
            "dueDate": "2026-10-10T23:59:00",
            "division": "B",
            "totalPoints": 100
        }
        res_assign = client.post("/api/assignments", json=assign_payload)
        assert res_assign.status_code == 201, f"Create assignment failed: {res_assign.get_json()}"
        assign_id = res_assign.get_json()["data"]["id"]
        print(f"✓ Faculty created Assignment ID={assign_id}: '{assign_payload['title']}' for CS601 Div B")
        client.post("/api/auth/logout")

        # Student views and submits assignment
        client.post("/api/auth/login", json={"email": "rahul.test@campus.edu", "password": "9876543299", "role": "student"})
        stu_assigns = client.get("/api/assignments").get_json()["data"]
        assert any(a["id"] == assign_id for a in stu_assigns), "Student should see CS601 Div A assignment!"
        print(f"✓ Student listed scoped assignment ID={assign_id}.")

        sub_res = client.post(f"/api/assignments/{assign_id}/submit", json={
            "submissionText": "Submitted hospital schema 3NF normalization report with ER diagram links."
        })
        assert sub_res.status_code == 201, f"Submit assignment failed: {sub_res.get_json()}"
        print(f"✓ Student submitted coursework for assignment ID={assign_id}.")
        client.post("/api/auth/logout")

        # Faculty grades student submission
        client.post("/api/auth/login", json={"email": "anita.test@campus.edu", "password": "9876543288", "role": "faculty"})
        grade_res = client.post(f"/api/assignments/{assign_id}/grade", json={
            "studentId": "STU2026999",
            "grade": 96.0,
            "feedback": "Excellent work on Boyce-Codd Normal Form decomposition."
        })
        assert grade_res.status_code == 200, f"Grade submission failed: {grade_res.get_json()}"
        assert grade_res.get_json()["data"]["grade"] == 96.0
        assert grade_res.get_json()["data"]["status"] == "graded"
        print(f"✓ Faculty graded submission: 96/100, Feedback: '{grade_res.get_json()['data']['feedback']}'")
        client.post("/api/auth/logout")

        print("\n=== ALL E2E VERIFICATIONS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    run_tests()
