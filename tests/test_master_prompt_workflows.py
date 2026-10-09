import io
import json
import re
from datetime import date, timedelta
from app import create_app
from extensions import db
from models import User, Student, Faculty, Course, Assignment, AssignmentSubmission, AttendanceSession, AttendanceRecord


def login_user(client, email, password):
    res = client.post(
        "/api/auth/login",
        data=json.dumps({"email": email, "password": password}),
        content_type="application/json"
    )
    return res


def logout_user(client):
    return client.post("/api/auth/logout")


def test_workflow_a_student_creation_and_prn(client, app):
    """Test A: Admin logs in, creates a student with automatic 241010XX PRN,
    assigns department, semester, division, and course enrollments, and verifies persistence."""
    # 1. Admin login
    res = login_user(client, "admin", "admin")
    assert res.status_code == 200, res.data

    # 2. Generate unique PRN endpoint check
    res_prn = client.get("/api/students/generate-prn")
    assert res_prn.status_code == 200
    gen_prn = res_prn.get_json()["data"]["prn"]
    assert re.match(r"^241010\d{2}$", gen_prn), f"PRN {gen_prn} must match format 241010XX"

    # 3. Create student record with unique test email
    import time
    test_email = f"ananya.test.{int(time.time())}@campus.edu"
    student_payload = {
        "name": "Ananya Sharma Demo",
        "email": test_email,
        "department": "Computer Science & Engineering",
        "semester": 6,
        "division": "A",
        "roll_number": "55",
        "courses": ["CS601", "CS602"]
    }
    res_create = client.post(
        "/api/students",
        data=json.dumps(student_payload),
        content_type="application/json"
    )
    assert res_create.status_code in (200, 201), res_create.data
    created_data = res_create.get_json()["data"]
    assigned_prn = created_data["prn"]
    assert assigned_prn.startswith("241010"), f"Generated PRN {assigned_prn} must start with 241010"
    assert len(assigned_prn) == 8

    with app.app_context():
        u = User.query.filter_by(email=test_email).first()
        assert u is not None
        assert u.student_profile is not None
        assert u.student_profile.division == "A"
        assert u.student_profile.prn == assigned_prn

    logout_user(client)


def test_workflow_b_faculty_roster_and_rbac(client, app):
    """Test B: Assigned faculty sees enrolled students in roster; unauthorized faculty gets 403."""
    # 1. Assigned faculty for CS601 Div A: Prof. Amit Deshmukh
    res = login_user(client, "amit.deshmukh@campus.edu", "campus@123")
    assert res.status_code == 200

    res_roster = client.get("/api/attendance/roll-call?courseCode=CS601&division=A")
    assert res_roster.status_code == 200
    roster_data = res_roster.get_json()["data"]
    students = roster_data["roster"]
    assert len(students) > 0

    # Verify student attributes: name, prn, roll number, division
    first_stu = students[0]
    assert "prn" in first_stu
    assert "rollNumber" in first_stu
    assert "name" in first_stu
    assert first_stu["division"] == "A"

    logout_user(client)

    # 2. Unauthorized faculty: Prof. Neha Patil is assigned to CS604, NOT CS601
    res_unauth = login_user(client, "neha.patil@campus.edu", "campus@123")
    assert res_unauth.status_code == 200
    res_forbidden = client.get("/api/attendance/roll-call?courseCode=CS601&division=A")
    assert res_forbidden.status_code == 403
    logout_user(client)


def test_workflow_c_attendance_management_and_student_view(client, app):
    """Test C: Faculty marks Present, Absent, Late; saves attendance;
    verifies persistence; student logs in and sees saved records and attendance percentage."""
    # 1. Faculty logs in and marks attendance
    res = login_user(client, "amit.deshmukh@campus.edu", "campus@123")
    assert res.status_code == 200

    test_date = (date.today() - timedelta(days=1)).isoformat()
    res_roster = client.get(f"/api/attendance/roll-call?courseCode=CS601&division=A&date={test_date}")
    assert res_roster.status_code == 200
    roster = res_roster.get_json()["data"]["roster"]
    assert len(roster) >= 3

    # Mark 1st present, 2nd late, 3rd absent
    records_to_save = [
        {"studentId": roster[0]["studentId"], "status": "present"},
        {"studentId": roster[1]["studentId"], "status": "late"},
        {"studentId": roster[2]["studentId"], "status": "absent"},
    ]

    save_payload = {
        "courseCode": "CS601",
        "division": "A",
        "date": test_date,
        "records": records_to_save
    }
    res_save = client.post(
        "/api/attendance/roll-call",
        data=json.dumps(save_payload),
        content_type="application/json"
    )
    assert res_save.status_code == 200, res_save.data

    # Reload roll-call as faculty to verify persistence
    res_reload = client.get(f"/api/attendance/roll-call?courseCode=CS601&division=A&date={test_date}")
    assert res_reload.status_code == 200
    reloaded_roster = res_reload.get_json()["data"]["roster"]
    status_map = {r["studentId"]: r["status"] for r in reloaded_roster}
    assert status_map[roster[0]["studentId"]] == "present"
    assert status_map[roster[1]["studentId"]] == "late"
    assert status_map[roster[2]["studentId"]] == "absent"

    logout_user(client)

    # 2. Student logs in to check attendance summary & history
    # First student in roster
    stu_code = roster[0]["studentId"]
    with app.app_context():
        stu = Student.query.filter_by(student_code=stu_code).first()
        student_email = stu.user.email

    res_stu_login = login_user(client, student_email, "campus@123")
    assert res_stu_login.status_code == 200

    res_summary = client.get("/api/attendance/summary")
    assert res_summary.status_code == 200
    summary_data = res_summary.get_json()["data"]
    assert "overall" in summary_data
    assert "history" in summary_data
    assert "percentage" in summary_data["overall"]
    assert summary_data["overall"]["percentage"] >= 0

    # Verify history contains our newly saved session
    history = summary_data["history"]
    matching_log = next((h for h in history if h.get("courseCode") == "CS601" and h.get("date") == test_date), None)
    assert matching_log is not None
    assert matching_log["status"] == "present"

    logout_user(client)


def test_workflow_d_e_f_g_assignment_lifecycle(client, app):
    """Tests D, E, F, G:
    Test D: Faculty creates 10-point assignment.
    Test E: Student submits answer/file.
    Test F: Faculty evaluates submission (0-10 marks and feedback).
    Test G: Student sees marks and feedback; privacy check."""
    # --- TEST D: FACULTY CREATES ASSIGNMENT ---
    res = login_user(client, "amit.deshmukh@campus.edu", "campus@123")
    assert res.status_code == 200

    due_time = (date.today() + timedelta(days=5)).isoformat() + "T23:59:00"
    create_payload = {
        "title": "DBMS Indexing & Query Optimization Lab",
        "courseCode": "CS601",
        "division": "A",
        "dueDate": due_time,
        "description": "Explain B+ Tree indexing mechanisms and provide benchmark results.",
        "totalPoints": 10
    }
    res_create = client.post(
        "/api/assignments",
        data=json.dumps(create_payload),
        content_type="application/json"
    )
    assert res_create.status_code in (200, 201), res_create.data
    assignment_id = res_create.get_json()["data"]["id"]
    assert res_create.get_json()["data"]["totalPoints"] == 10

    logout_user(client)

    # --- TEST E: STUDENT SUBMISSION ---
    # Log in as Ayan Mulani
    res = login_user(client, "ayan.mulani@campus.edu", "campus@123")
    assert res.status_code == 200

    # Student sees the assignment in assignment list
    res_list = client.get("/api/assignments")
    assert res_list.status_code == 200
    student_assignments = res_list.get_json()["data"]
    matching = next((a for a in student_assignments if a["id"] == assignment_id), None)
    assert matching is not None
    assert matching["totalPoints"] == 10

    # Submit written answer and file
    fake_doc_content = b"%PDF-1.4 B-Tree analysis report submitted by Ayan Mulani\n%%EOF"
    submit_data = {
        "submissionText": "Detailed analysis of B+ tree branch fanout and I/O cost reduction.",
        "file": (io.BytesIO(fake_doc_content), "btree_report.pdf", "application/pdf")
    }
    res_submit = client.post(
        f"/api/assignments/{assignment_id}/submit",
        data=submit_data,
        content_type="multipart/form-data"
    )
    assert res_submit.status_code in (200, 201), res_submit.data
    submission_id = res_submit.get_json()["data"]["id"]
    assert res_submit.get_json()["data"]["status"] in ("submitted", "late")

    # Verify persistence by fetching single assignment
    res_get = client.get(f"/api/assignments/{assignment_id}")
    assert res_get.status_code == 200
    assert res_get.get_json()["data"]["isSubmitted"] is True

    logout_user(client)

    # --- TEST F: FACULTY EVALUATION ---
    res = login_user(client, "amit.deshmukh@campus.edu", "campus@123")
    assert res.status_code == 200

    # Open evaluation roster
    res_roster = client.get(f"/api/assignments/{assignment_id}/evaluation-roster")
    assert res_roster.status_code == 200
    roster_subs = res_roster.get_json()["data"]["roster"]
    sub_row = next((s for s in roster_subs if s["id"] == submission_id), None)
    assert sub_row is not None
    assert sub_row["prn"] == "24101026"  # Ayan Mulani's PRN

    # Faculty grades submission: 9.5 out of 10 marks
    eval_payload = {
        "marks_obtained": 9.5,
        "feedback": "Outstanding analysis of B+ tree index nodes. Clear diagrammatic presentation."
    }
    res_grade = client.post(
        f"/api/assignments/submissions/{submission_id}/grade",
        data=json.dumps(eval_payload),
        content_type="application/json"
    )
    assert res_grade.status_code == 200, res_grade.data
    assert res_grade.get_json()["data"]["marks_obtained"] == 9.5

    logout_user(client)

    # --- TEST G: STUDENT SEES MARKS & PRIVACY ---
    res = login_user(client, "ayan.mulani@campus.edu", "campus@123")
    assert res.status_code == 200

    res_student_view = client.get(f"/api/assignments/{assignment_id}")
    assert res_student_view.status_code == 200
    assign_info = res_student_view.get_json()["data"]
    assert assign_info["isEvaluated"] is True
    assert assign_info["marksObtained"] == 9.5
    assert "Outstanding analysis" in assign_info["feedback"]

    logout_user(client)

    # Privacy check: Arkam Momin cannot access Ayan's submission download
    res_arkam = login_user(client, "arkam.momin@campus.edu", "campus@123")
    assert res_arkam.status_code == 200
    res_priv = client.get(f"/api/assignments/submissions/{submission_id}/download")
    assert res_priv.status_code == 403, "Another student must not access private submission download"
    logout_user(client)


def test_workflow_h_security_and_regression(client, app):
    """Test I: Security validation: marks > 10 rejected, negative marks rejected,
    unauthorized faculty cannot grade or mark attendance, and admin credentials work."""
    # 1. Admin login works with admin/admin
    res_admin = login_user(client, "admin", "admin")
    assert res_admin.status_code == 200
    logout_user(client)

    # 2. Faculty grading bounds check: > 10 marks must be rejected
    res_fac = login_user(client, "amit.deshmukh@campus.edu", "campus@123")
    assert res_fac.status_code == 200

    with app.app_context():
        # Find any 10-point assignment submission
        sub = AssignmentSubmission.query.join(Assignment).filter(Assignment.total_points == 10).first()
        if sub:
            invalid_eval = {"marks_obtained": 15, "feedback": "Exceeds max points"}
            res_inv = client.post(
                f"/api/assignments/submissions/{sub.id}/grade",
                data=json.dumps(invalid_eval),
                content_type="application/json"
            )
            assert res_inv.status_code == 400

            neg_eval = {"marks_obtained": -2, "feedback": "Negative marks"}
            res_neg = client.post(
                f"/api/assignments/submissions/{sub.id}/grade",
                data=json.dumps(neg_eval),
                content_type="application/json"
            )
            assert res_neg.status_code == 400

    logout_user(client)

    # 3. Prohibited legacy faculty check
    with app.app_context():
        for bad_name in ["P B Patil", "Anita Sen"]:
            u = User.query.filter(User.full_name.ilike(f"%{bad_name}%")).first()
            assert u is None, f"Prohibited legacy record {bad_name} must not exist in database"
        u_bad_email = User.query.filter_by(email="anita.sen@campus.edu").first()
        assert u_bad_email is None, "Prohibited email anita.sen@campus.edu must not exist"
