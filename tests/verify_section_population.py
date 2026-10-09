import sys
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app import create_app
from extensions import db
from models import (
    User, Department, Course, Enrollment, Student, Faculty, FacultyAssignment,
    AttendanceSession, AttendanceRecord, Result, Assignment, AssignmentSubmission
)


def verify_section_population():
    print("=" * 80)
    print("CAMPUS CONNECT ERP -- 10-STUDENT SECTION POPULATION AUDIT & VERIFICATION")
    print("=" * 80)

    app = create_app()
    client = app.test_client()

    with app.app_context():
        # ---------------------------------------------------------------------
        # 1. DEPARTMENTS, SEMESTERS & DIVISIONS AUDIT
        # ---------------------------------------------------------------------
        print("\n[CHECK 1] Configured Academic Units:")
        depts = Department.query.order_by(Department.id).all()
        print(f"  * Total Configured Departments: {len(depts)}")
        for d in depts:
            print(f"    - ID {d.id} | Code: {d.code:5s} | Name: {d.name}")

        div_query = (
            db.session.query(
                Department.code, Student.semester, Student.division, db.func.count(Student.id)
            )
            .join(Department, Student.department_id == Department.id)
            .group_by(Department.code, Student.semester, Student.division)
            .order_by(Department.code, Student.semester, Student.division)
            .all()
        )

        distinct_semesters = set(item[1] for item in div_query)
        print(f"  * Total Configured Semesters: {len(distinct_semesters)} ({sorted(distinct_semesters)})")
        print(f"  * Total Configured Divisions: {len(div_query)}")

        print("\n[CHECK 2] Student Counts by Academic Division:")
        for d_code, sem, div, cnt in div_query:
            status = "PASSED (>= 10)" if cnt >= 10 else "FAILED (< 10)"
            print(f"    - {d_code} Semester {sem} Division {div}: {cnt} active students [{status}]")
            assert cnt >= 10, f"Division {d_code} Sem {sem} Div {div} has only {cnt} students!"

        # ---------------------------------------------------------------------
        # 2. PRESERVED MANDATORY STUDENTS
        # ---------------------------------------------------------------------
        print("\n[CHECK 3] Preserved Mandatory Named Students in CSE Sem 6 Div A:")
        mandatory_students = [
            ("Ayan Mulani", "24101026", "01"),
            ("Arkam Momin", "24101035", "02"),
            ("Piyush Mane", "24101092", "03"),
            ("Ankush Saini", "24101006", "04"),
        ]
        for name, expected_prn, expected_roll in mandatory_students:
            user = User.query.filter(User.full_name.ilike(name)).first()
            assert user is not None, f"Mandatory student {name} not found in User table!"
            stu = Student.query.filter_by(user_id=user.id).first()
            assert stu is not None, f"Student profile for {name} not found!"
            assert stu.prn == expected_prn, f"PRN mismatch for {name}: expected {expected_prn}, got {stu.prn}"
            assert stu.roll_number == expected_roll, f"Roll mismatch for {name}: expected {expected_roll}, got {stu.roll_number}"
            assert stu.department.code == "CSE", f"Department mismatch for {name}"
            assert stu.semester == 6, f"Semester mismatch for {name}"
            assert stu.division == "A", f"Division mismatch for {name}"
            print(f"    [OK] {name:15s} | PRN: {stu.prn} | Roll: {stu.roll_number} | CSE Sem 6 Div A [VERIFIED]")

        # ---------------------------------------------------------------------
        # 3. PRN INTEGRITY, FORMAT & CAPACITY
        # ---------------------------------------------------------------------
        print("\n[CHECK 4] PRN Uniqueness, Format & Pool Capacity:")
        all_students = Student.query.all()
        prns = [s.prn for s in all_students if s.prn]
        assert len(prns) == len(set(prns)), "Duplicate PRNs detected in database!"
        
        prn_24_pattern = [p for p in prns if p.startswith("241010") and len(p) == 8 and p[6:].isdigit()]
        print(f"  * Total active students: {len(all_students)}")
        print(f"  * Students with PRN format 241010XX: {len(prn_24_pattern)}")
        print(f"  * PRN Capacity Used: {len(prn_24_pattern)} / 100")
        print(f"  * PRN Capacity Remaining: {100 - len(prn_24_pattern)} available slots")
        assert len(prn_24_pattern) <= 100, "PRN allocation exceeded 100 capacity pool!"
        print("  [OK] Database-level uniqueness confirmed for all student PRNs.")

        # ---------------------------------------------------------------------
        # 4. ENROLLMENTS & FACULTY ASSIGNMENTS
        # ---------------------------------------------------------------------
        print("\n[CHECK 5] Course Enrollments & Faculty Assignments:")
        for stu in all_students:
            enrs = Enrollment.query.filter_by(student_id=stu.id).count()
            assert enrs > 0, f"Student {stu.student_code} ({stu.user.full_name}) has NO course enrollments!"

        total_enrs = Enrollment.query.count()
        total_fas = FacultyAssignment.query.count()
        print(f"  * Total active enrollments: {total_enrs}")
        print(f"  * Total faculty assignments: {total_fas}")

        # Check Division B has faculty assigned
        div_b_fas = FacultyAssignment.query.filter_by(division="B").all()
        assert len(div_b_fas) > 0, "No faculty assigned to Division B!"
        print(f"  * Division B Faculty Assignments: {len(div_b_fas)} assignments verified.")

        # Verify Prof. Amit Deshmukh is strictly assigned ONLY to CS601 Div A
        fac_amit = Faculty.query.filter_by(faculty_code="FAC2020021").first()
        amit_fas = FacultyAssignment.query.filter_by(faculty_id=fac_amit.id).all()
        for fa in amit_fas:
            assert fa.division == "A", f"Prof. Amit Deshmukh must NOT be assigned to Div {fa.division}!"
            assert fa.course.code == "CS601", f"Prof. Amit Deshmukh must NOT be assigned to {fa.course.code}!"
        print("  [OK] Prof. Amit Deshmukh (FAC2020021) strictly restricted to CS601 Div A.")

    # -------------------------------------------------------------------------
    # 5. ATTENDANCE WORKFLOW ACROSS POPULATED DIVISIONS
    # -------------------------------------------------------------------------
    print("\n[CHECK 6] Testing Attendance Roster & Marking across Populated Divisions:")
    
    # 1. Faculty login (Prof. Rajesh Verma for CS602 Div A & Div B)
    res = client.post("/api/auth/login", json={
        "email": "rajesh.verma@campus.edu", "password": "campus@123", "role": "faculty"
    })
    assert res.status_code == 200, "Prof. Rajesh Verma login failed"
    rajesh_token = res.get_json()["sessionToken"]

    # 2. Test Division B roll-call roster contains 10 students
    res = client.get("/api/attendance/roll-call?courseCode=CS602&division=B", headers={"X-Session-Token": rajesh_token})
    assert res.status_code == 200, f"Division B roll call failed: {res.get_json()}"
    roster_b = res.get_json()["data"]["roster"]
    assert len(roster_b) == 10, f"Expected 10 students in CS602 Div B roster, got {len(roster_b)}"
    print(f"  [OK] CS602 Division B loaded 10-student roster successfully.")

    # 3. Mark Present, Absent, Late in Division B
    att_payload = {
        "courseCode": "CS602",
        "division": "B",
        "date": "2026-10-09",
        "records": [
            {"studentId": roster_b[0]["studentId"], "status": "present"},
            {"studentId": roster_b[1]["studentId"], "status": "late"},
            {"studentId": roster_b[2]["studentId"], "status": "absent"},
        ]
    }
    res = client.post("/api/attendance/roll-call", json=att_payload, headers={"X-Session-Token": rajesh_token})
    assert res.status_code == 200, f"Marking attendance in Div B failed: {res.get_json()}"
    print("  [OK] Faculty successfully marked Present, Late, Absent in Division B.")

    # 4. Student checks personal attendance summary
    target_stu_email = roster_b[0]["studentId"]
    with app.app_context():
        stu_obj = Student.query.filter_by(student_code=target_stu_email).first()
        stu_user_email = stu_obj.user.email

    res = client.post("/api/auth/login", json={
        "email": stu_user_email, "password": "campus@123", "role": "student"
    })
    assert res.status_code == 200, f"Student {stu_user_email} login failed"
    stu_token = res.get_json()["sessionToken"]

    res = client.get("/api/attendance/summary", headers={"X-Session-Token": stu_token})
    assert res.status_code == 200, "Student attendance summary failed"
    att_summary = res.get_json()["data"]
    assert "overall" in att_summary
    assert "rows" in att_summary
    print(f"  [OK] Student in Division B ({stu_user_email}) retrieved live attendance calculation: {att_summary['overall']['percentage']}%")

    # -------------------------------------------------------------------------
    # 6. ASSIGNMENTS & RESULTS WORKFLOW
    # -------------------------------------------------------------------------
    print("\n[CHECK 7] Testing Assignment Submission & Evaluation Workflow:")
    # Student views assignments for their division
    res = client.get("/api/assignments", headers={"X-Session-Token": stu_token})
    assert res.status_code == 200
    assignments = res.get_json()["data"]
    assert len(assignments) > 0, "Student in Div B sees 0 assignments!"
    target_asgn = assignments[0]
    print(f"  [OK] Student visible coursework: '{target_asgn['title']}' (Points: {target_asgn['totalPoints']})")

    # Student submits assignment
    sub_res = client.post(f"/api/assignments/{target_asgn['id']}/submit", json={
        "submissionText": "Detailed problem analysis and solution notes for demonstration.",
        "fileName": "demo_solution.pdf"
    }, headers={"X-Session-Token": stu_token})
    assert sub_res.status_code in (200, 201), f"Assignment submission failed: {sub_res.get_json()}"
    sub_id = sub_res.get_json()["data"]["id"]
    print(f"  [OK] Student successfully submitted assignment (Submission ID: {sub_id})")

    # Faculty grades submission (0-10 marks)
    eval_res = client.post(f"/api/assignments/submissions/{sub_id}/grade", json={
        "grade": 9.5,
        "feedback": "Outstanding solution methodology. All test cases passed."
    }, headers={"X-Session-Token": rajesh_token})
    assert eval_res.status_code == 200, f"Faculty grading failed: {eval_res.get_json()}"
    print(f"  [OK] Faculty graded submission: 9.5 / 10 marks with feedback.")

    # Student views saved grade
    my_sub_res = client.get(f"/api/assignments/{target_asgn['id']}", headers={"X-Session-Token": stu_token})
    assert my_sub_res.status_code == 200
    my_sub_data = my_sub_res.get_json()["data"]["mySubmission"]
    assert my_sub_data["grade"] == 9.5
    assert "Outstanding" in my_sub_data["feedback"]
    print("  [OK] Student verified their saved score and feedback.")

    # -------------------------------------------------------------------------
    # 7. SECURITY & RBAC ISOLATION
    # -------------------------------------------------------------------------
    print("\n[CHECK 8] Security, RBAC & Parameter Manipulation Protection:")
    res = client.post("/api/auth/login", json={
        "email": "amit.deshmukh@campus.edu", "password": "campus@123", "role": "faculty"
    })
    amit_token = res.get_json()["sessionToken"]

    # Amit Deshmukh blocked from accessing Division B roll call
    res = client.get("/api/attendance/roll-call?courseCode=CS601&division=B", headers={"X-Session-Token": amit_token})
    assert res.status_code == 403, f"Expected 403 for unauthorized division, got {res.status_code}"
    print("  [OK] Faculty blocked from unassigned Division B: HTTP 403 Forbidden.")

    # Student blocked from accessing other student's profile
    res = client.get("/api/students/STU24101", headers={"X-Session-Token": stu_token})
    assert res.status_code == 403, f"Expected 403 for private student profile, got {res.status_code}"
    print("  [OK] Student privacy enforced: HTTP 403 Forbidden on foreign student profile.")

    # -------------------------------------------------------------------------
    # 8. ADMIN CREATING NEW STUDENT AND APPEARING IN ROSTER
    # -------------------------------------------------------------------------
    print("\n[CHECK 9] Admin Interface New Student Provisioning & Faculty Roster Sync:")
    admin_login = client.post("/api/auth/login", json={
        "username": "admin", "password": "admin", "role": "admin"
    })
    assert admin_login.status_code == 200, "Admin login failed"
    admin_token = admin_login.get_json()["sessionToken"]

    new_stu_payload = {
        "name": "Audit New Student CSE",
        "email": "audit.new.cse@campus.edu",
        "phone": "9823999991",
        "department": "Computer Science & Engineering",
        "year": "3rd Year",
        "semester": 6,
        "division": "B",
    }
    create_res = client.post("/api/students", json=new_stu_payload, headers={"X-Session-Token": admin_token})
    assert create_res.status_code in (200, 201), f"Admin student creation failed: {create_res.get_json()}"
    new_stu_data = create_res.get_json()["data"]
    created_prn = new_stu_data.get("prn")
    print(f"  [OK] Admin created new student: {new_stu_data['name']} (PRN: {created_prn}, Division: B)")

    # Verify student now appears in CS602 Div B roster
    roster_refresh = client.get("/api/attendance/roll-call?courseCode=CS602&division=B", headers={"X-Session-Token": rajesh_token})
    assert roster_refresh.status_code == 200
    updated_roster = roster_refresh.get_json()["data"]["roster"]
    assert any(s["studentId"] == new_stu_data["studentCode"] or s["prn"] == created_prn for s in updated_roster), (
        "Newly created student does not appear in faculty roster!"
    )
    print(f"  [OK] Newly created student immediately appears in Faculty attendance roster! (Roster size: {len(updated_roster)})")

    # Clean up audit test student
    with app.app_context():
        test_u = User.query.filter_by(email="audit.new.cse@campus.edu").first()
        if test_u:
            test_s = Student.query.filter_by(user_id=test_u.id).first()
            if test_s:
                Enrollment.query.filter_by(student_id=test_s.id).delete()
                db.session.delete(test_s)
            db.session.delete(test_u)
            db.session.commit()

    print("\n" + "=" * 80)
    print("ALL 9 VERIFICATION AND ACCEPTANCE CHECKS PASSED 100% CLEANLY!")
    print("=" * 80)


if __name__ == "__main__":
    verify_section_population()
