"""
Seeds the database with demo data that mirrors the names, IDs, departments,
and courses for Campus Connect so the UI displays authentic ERP data on day one.
"""
import os
import sys
from pathlib import Path

# Ensure project root is on Python search path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

from extensions import db
from models import (
    Department, Course, User, Student, Faculty, FacultyAssignment, Enrollment,
    Notice, Event, StudyMaterial, LeaveRequest, Assignment,
)

DEMO_PASSWORD = "campus@123"


def _get_or_create_department(name, code):
    dept = Department.query.filter_by(name=name).first()
    if not dept:
        dept = Department(name=name, code=code)
        db.session.add(dept)
        db.session.flush()
    return dept


def _get_or_create_user(email, name, role, password=DEMO_PASSWORD, phone=None):
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(email=email, full_name=name, role=role, phone=phone)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
    elif phone and not user.phone:
        user.phone = phone
    return user


def ensure_default_admin():
    """Idempotently ensures the default administrator account exists.

    Default Admin credentials:
      Username: admin (or email: admin@campus.edu)
      Password: admin (stored securely using Flask password hashing)
      Role: admin
    """
    admin_user = User.query.filter(
        db.or_(User.email.ilike("admin@campus.edu"), User.email.ilike("admin"))
    ).first()

    if not admin_user:
        admin_user = User(
            email="admin@campus.edu",
            full_name="System Administrator",
            role="admin",
            phone="9876500000",
            is_active=True,
        )
        admin_user.set_password("admin")
        db.session.add(admin_user)
        db.session.commit()
    else:
        changed = False
        if admin_user.role != "admin":
            admin_user.role = "admin"
            changed = True
        if not admin_user.is_active:
            admin_user.is_active = True
            changed = True
        if not admin_user.check_password("admin"):
            admin_user.set_password("admin")
            changed = True
        if changed:
            db.session.commit()
    return admin_user


def run_seed():
    print("Beginning database seed...")
    cse = _get_or_create_department("Computer Science & Engineering", "CSE")
    ece = _get_or_create_department("Electronics & Communication", "ECE")
    mech = _get_or_create_department("Mechanical Engineering", "MECH")
    civil = _get_or_create_department("Civil Engineering", "CE")
    db.session.flush()

    # --- Faculty -------------------------------------------------------
    fac1_user = _get_or_create_user("anita.sen@campus.edu", "P B Patil", "faculty", phone="9876500001")
    fac1 = Faculty.query.filter_by(user_id=fac1_user.id).first() or Faculty(
        user_id=fac1_user.id, faculty_code="FAC2018042", department_id=cse.id,
        designation="Associate Professor",
    )
    db.session.add(fac1)

    fac2_user = _get_or_create_user("rajesh.verma@campus.edu", "Prof. Rajesh Verma", "faculty", phone="9876500002")
    fac2 = Faculty.query.filter_by(user_id=fac2_user.id).first() or Faculty(
        user_id=fac2_user.id, faculty_code="FAC2019018", department_id=cse.id,
        designation="Assistant Professor",
    )
    db.session.add(fac2)
    db.session.flush()

    # --- Admin -----------------------------------------------------------
    ensure_default_admin()

    # --- Students --------------------------------------------------------
    students_data = [
        ("rahul@campus.edu", "John Snow", "STU2024001", cse, "3rd Year", 6, "A", "32", "PRN2024001", "9876500011"),
        ("priya.patel@campus.edu", "Priya Patel", "STU2024002", cse, "3rd Year", 6, "A", "33", "PRN2024002", "9876500012"),
        ("aman.verma@campus.edu", "Aman Verma", "STU2023089", ece, "2nd Year", 4, "B", "15", "PRN2023089", "9876500013"),
        ("sneha.roy@campus.edu", "Sneha Roy", "STU2022014", mech, "4th Year", 8, "A", "07", "PRN2022014", "9876500014"),
    ]
    students = {}
    for email, name, code, dept, year, sem, div, roll, prn, phone in students_data:
        u = _get_or_create_user(email, name, "student", phone=phone)
        s = Student.query.filter_by(user_id=u.id).first()
        if not s:
            s = Student(
                user_id=u.id, student_code=code, department_id=dept.id,
                year_label=year, semester=sem, division=div, roll_number=roll, prn=prn,
            )
            db.session.add(s)
        else:
            s.division = div
            s.roll_number = roll
            s.prn = prn
        students[code] = s
    db.session.flush()

    # --- Courses -----------------------------------------------------------
    courses_data = [
        ("CS601", "Database Management Systems", 4, "core", 6, "Room 304", fac1.id, 80),
        ("CS602", "Computer Networks & Security", 4, "core", 6, "Room 202", fac2.id, 65),
        ("CS603", "Design & Analysis of Algorithms", 4, "core", 6, "Room 301", None, 75),
        ("CS604", "Software Engineering & Agile", 3, "core", 6, "Room 105", None, 90),
        ("CS691", "Database & SQL Practical Lab", 2, "lab", 6, "Lab Block 2", fac1.id, 85),
        ("CS692", "Network Socket Programming Lab", 2, "lab", 6, "Lab Block 4", fac2.id, 70),
    ]
    courses = {}
    for code, title, credits, category, sem, room, instr_id, coverage in courses_data:
        c = Course.query.filter_by(code=code).first() or Course(
            code=code, title=title, credits=credits, category=category,
            semester=sem, room=room, department_id=cse.id,
            instructor_id=instr_id, syllabus_coverage=coverage,
        )
        db.session.add(c)
        courses[code] = c
    db.session.flush()

    # --- Faculty Relational Teaching Assignments --------------------------
    assignments_data = [
        (fac1.id, courses["CS601"].id, cse.id, "3rd Year", 6, "A"),
        (fac1.id, courses["CS601"].id, cse.id, "3rd Year", 6, "B"),
        (fac1.id, courses["CS691"].id, cse.id, "3rd Year", 6, "A"),
        (fac2.id, courses["CS602"].id, cse.id, "3rd Year", 6, "A"),
        (fac2.id, courses["CS692"].id, cse.id, "3rd Year", 6, "A"),
    ]
    for fid, cid, did, yr, sem, div in assignments_data:
        exists = FacultyAssignment.query.filter_by(
            faculty_id=fid, course_id=cid, semester=sem, division=div
        ).first()
        if not exists:
            db.session.add(FacultyAssignment(
                faculty_id=fid, course_id=cid, department_id=did,
                year_label=yr, semester=sem, division=div,
            ))

    # --- Enrollments ------------------------------------------------------
    for code in courses:
        for scode in ("STU2024001", "STU2024002"):
            exists = Enrollment.query.filter_by(
                student_id=students[scode].id, course_id=courses[code].id
            ).first()
            if not exists:
                db.session.add(Enrollment(student_id=students[scode].id, course_id=courses[code].id))

    # --- Welcome Notice ---------------------------------------------------
    admin_user = User.query.filter_by(email="admin@campus.edu").first()
    if not Notice.query.first():
        db.session.add(Notice(
            title="Welcome to Campus Connect",
            category="General",
            body="The portal is now backed by a real database. Demo accounts: "
                 "admin@campus.edu, anita.sen@campus.edu, rahul@campus.edu "
                 f"(password: {DEMO_PASSWORD}).",
            posted_by_id=admin_user.id,
            department_id=None,
            year_label=None,
            semester=None,
            division="All",
        ))

    # --- Sample Study Material ---------------------------------------------
    if not StudyMaterial.query.first():
        sample_pdf_bytes = (
            b"%PDF-1.4\n"
            b"%\xe2\xe3\xcf\xd3\n"
            b"1 0 obj\n"
            b"<< /Type /Catalog /Pages 2 0 R >>\n"
            b"endobj\n"
            b"2 0 obj\n"
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>\n"
            b"endobj\n"
            b"3 0 obj\n"
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>\n"
            b"endobj\n"
            b"4 0 obj\n"
            b"<< /Length 85 >>\n"
            b"stream\n"
            b"BT /F1 18 Tf 50 700 Td (Campus Connect: DBMS Module 1 - Relational Algebra & Normalization) Tj ET\n"
            b"endstream\n"
            b"endobj\n"
            b"xref\n"
            b"0 5\n"
            b"0000000000 65535 f \n"
            b"0000000015 00000 n \n"
            b"0000000068 00000 n \n"
            b"0000000125 00000 n \n"
            b"0000000216 00000 n \n"
            b"trailer\n"
            b"<< /Size 5 /Root 1 0 R >>\n"
            b"startxref\n"
            b"350\n"
            b"%%EOF\n"
        )
        db.session.add(StudyMaterial(
            title="Module 1: Relational Algebra & SQL Normalization",
            category="Notes",
            course_id=courses["CS601"].id,
            department_id=cse.id,
            year_label="3rd Year",
            semester=6,
            division="A",
            file_name="Module_1_DBMS_Notes.pdf",
            file_size_bytes=len(sample_pdf_bytes),
            file_data=sample_pdf_bytes,
            file_path=None,
            mime_type="application/pdf",
            uploaded_by_id=fac1_user.id,
        ))

    # --- Sample Coursework Assignment ---------------------------------------
    if not Assignment.query.first():
        from datetime import datetime, timezone, timedelta
        db.session.add(Assignment(
            title="Assignment 1: Relational Schema & Normalization",
            description="Complete the database normalization exercises for Units 1-3. Submit diagrams in PDF.",
            course_id=courses["CS601"].id,
            faculty_id=fac1.id,
            year_label="3rd Year",
            semester=6,
            division="A",
            due_date=datetime.now(timezone.utc) + timedelta(days=14),
            total_points=100,
        ))

    # --- Sample Student Leave Request ---------------------------------------
    if not LeaveRequest.query.first():
        from datetime import date, timedelta
        rahul_student = students.get("STU2024001") or Student.query.first()
        if rahul_student:
            db.session.add(LeaveRequest(
                student_id=rahul_student.id,
                leave_type="Academic",
                start_date=date.today() + timedelta(days=5),
                end_date=date.today() + timedelta(days=7),
                reason="Attending National Student Technology Symposium as a college representative.",
                status="pending",
            ))

    db.session.commit()
    print("Seed complete.")
    print("Default Admin Account:")
    print("  Username: admin (or admin@campus.edu)")
    print("  Password: admin")
    print(f"Demo login password for seeded accounts: {DEMO_PASSWORD}")
    print("  admin:   admin / admin@campus.edu (password: admin)")
    print("  faculty: anita.sen@campus.edu")
    print("  student: rahul@campus.edu")


if __name__ == "__main__":
    from app import create_app
    app = create_app()
    with app.app_context():
        run_seed()
