import io
from datetime import datetime, timezone, date, timedelta
from werkzeug.security import generate_password_hash
from extensions import db
from models import (
    User, Department, Course, Enrollment, Student, Faculty, FacultyAssignment,
    AttendanceSession, AttendanceRecord, Result, Notice, StudyMaterial, Event,
    LeaveRequest, Assignment, AssignmentSubmission
)

DEMO_PASSWORD = "campus@123"


def generate_unique_prn(max_attempts=300):
    """Generates a unique student PRN adhering to format 241010XX (prefix 241010 + 2 decimal digits 00-99).
    Enforces uniqueness at database level and rejects duplicates."""
    import random
    for _ in range(max_attempts):
        xx = random.randint(0, 99)
        candidate = f"241010{xx:02d}"
        if not Student.query.filter(db.or_(Student.prn == candidate, Student.student_code == candidate)).first():
            return candidate

    for xx in range(100):
        candidate = f"241010{xx:02d}"
        if not Student.query.filter(db.or_(Student.prn == candidate, Student.student_code == candidate)).first():
            return candidate

    raise RuntimeError("All 100 PRNs in 241010XX space are allocated.")


def ensure_default_admin():
    """Guarantees an active administrator account with login credentials:
    Username: admin
    Password: admin
    Role: admin
    Stored securely with password hashing."""
    admin = User.query.filter(
        db.or_(User.email.ilike("admin@campus.edu"), User.email.ilike("admin"))
    ).first()

    if not admin:
        admin = User(
            email="admin@campus.edu",
            full_name="System Administrator",
            phone="9876543210",
            role="admin",
            is_active=True,
        )
        admin.set_password("admin")
        db.session.add(admin)
        db.session.commit()
    else:
        admin.role = "admin"
        admin.is_active = True
        admin.set_password("admin")
        db.session.commit()

    return admin


def cleanup_old_demo_data():
    """Safely cleans any obsolete non-primary faculty accounts and explicitly removes prohibited legacy records."""
    # Module 2: Permanently remove prohibited legacy records
    prohibited_users = User.query.filter(
        db.or_(
            User.email.ilike("%anita.sen%"),
            User.full_name.ilike("%P B Patil%"),
            User.full_name.ilike("%P. B. Patil%"),
            User.full_name.ilike("%PB Patil%"),
        )
    ).all()
    for pu in prohibited_users:
        pfac = Faculty.query.filter_by(user_id=pu.id).first()
        if pfac:
            FacultyAssignment.query.filter_by(faculty_id=pfac.id).delete()
            Course.query.filter_by(instructor_id=pfac.id).update({"instructor_id": None})
            for s in AttendanceSession.query.filter_by(marked_by_id=pfac.id).all():
                AttendanceRecord.query.filter_by(session_id=s.id).delete()
                db.session.delete(s)
            Result.query.filter_by(entered_by_id=pfac.id).update({"entered_by_id": None})
            for a in Assignment.query.filter_by(faculty_id=pfac.id).all():
                AssignmentSubmission.query.filter_by(assignment_id=a.id).delete()
                db.session.delete(a)
            AssignmentSubmission.query.filter_by(graded_by_id=pfac.id).update({"graded_by_id": None})
            db.session.delete(pfac)
        StudyMaterial.query.filter_by(uploaded_by_id=pu.id).delete()
        Notice.query.filter_by(posted_by_id=pu.id).delete()
        Event.query.filter_by(created_by_id=pu.id).delete()
        db.session.delete(pu)
    db.session.commit()

    valid_faculty_emails = [
        "amit.deshmukh@campus.edu",
        "rajesh.verma@campus.edu",
        "neha.patil@campus.edu",
        "pooja.more@campus.edu",
        "snehal.kulkarni@campus.edu",
    ]
    obsolete_faculty_users = User.query.filter(
        User.role == "faculty",
        ~User.email.in_(valid_faculty_emails)
    ).all()

    for old_user in obsolete_faculty_users:
        old_faculty = Faculty.query.filter_by(user_id=old_user.id).first()
        if old_faculty:
            FacultyAssignment.query.filter_by(faculty_id=old_faculty.id).delete()
            Course.query.filter_by(instructor_id=old_faculty.id).update({"instructor_id": None})
            old_sessions = AttendanceSession.query.filter_by(marked_by_id=old_faculty.id).all()
            for s in old_sessions:
                AttendanceRecord.query.filter_by(session_id=s.id).delete()
                db.session.delete(s)
            Result.query.filter_by(entered_by_id=old_faculty.id).update({"entered_by_id": None})
            old_assignments = Assignment.query.filter_by(faculty_id=old_faculty.id).all()
            for a in old_assignments:
                AssignmentSubmission.query.filter_by(assignment_id=a.id).delete()
                db.session.delete(a)
            AssignmentSubmission.query.filter_by(graded_by_id=old_faculty.id).update({"graded_by_id": None})
            db.session.delete(old_faculty)

        StudyMaterial.query.filter_by(uploaded_by_id=old_user.id).delete()
        Notice.query.filter_by(posted_by_id=old_user.id).delete()
        Event.query.filter_by(created_by_id=old_user.id).delete()
        db.session.delete(old_user)
    db.session.commit()


def seed_departments():
    """Provisions canonical academic departments."""
    departments_spec = [
        ("Computer Science & Engineering", "CSE"),
        ("Electronics & Communication", "ECE"),
        ("Mechanical Engineering", "MECH"),
        ("Civil Engineering", "CE"),
    ]
    created = {}
    for name, code in departments_spec:
        dept = Department.query.filter(
            db.or_(Department.name.ilike(name), Department.code.ilike(code))
        ).first()
        if not dept:
            dept = Department(name=name, code=code)
            db.session.add(dept)
            db.session.flush()
        created[code] = dept
    db.session.commit()
    return created


def _get_or_create_user(email, full_name, role, phone=None, password=DEMO_PASSWORD):
    u = User.query.filter(User.email.ilike(email)).first()
    if not u:
        u = User(
            email=email,
            full_name=full_name,
            role=role,
            phone=phone,
            is_active=True,
        )
        u.set_password(password)
        db.session.add(u)
        db.session.flush()
    else:
        u.full_name = full_name
        u.role = role
        u.is_active = True
        if phone:
            u.phone = phone
        u.set_password(password)
    return u


def seed_faculty(departments):
    """Provisions exactly the 5 primary demo faculty accounts."""
    cse = departments["CSE"]
    faculty_spec = [
        ("amit.deshmukh@campus.edu", "Prof. Amit Deshmukh", "FAC2020021", "Associate Professor", "9820000001"),
        ("rajesh.verma@campus.edu", "Prof. Rajesh Verma", "FAC2019018", "Professor & Head", "9820000002"),
        ("neha.patil@campus.edu", "Prof. Neha Patil", "FAC2021034", "Assistant Professor", "9820000003"),
        ("pooja.more@campus.edu", "Prof. Pooja More", "FAC2022045", "Assistant Professor", "9820000004"),
        ("snehal.kulkarni@campus.edu", "Prof. Snehal Kulkarni", "FAC2023051", "Assistant Professor", "9820000005"),
    ]
    faculty_map = {}
    for email, name, code, designation, phone in faculty_spec:
        user = _get_or_create_user(email, name, "faculty", phone=phone)
        fac = Faculty.query.filter_by(faculty_code=code).first()
        if not fac:
            fac = Faculty(
                user_id=user.id,
                faculty_code=code,
                department_id=cse.id,
                designation=designation,
                status="active",
            )
            db.session.add(fac)
            db.session.flush()
        else:
            fac.user_id = user.id
            fac.department_id = cse.id
            fac.designation = designation
            fac.status = "active"
        faculty_map[code] = fac

    db.session.commit()
    return faculty_map


def seed_students(departments):
    """Provisions realistic student records including mandatory Module 1 students:
    Ayan Mulani, Arkam Momin, Piyush Mane, Ankush Saini, and Student 5 (Pending Name)
    with unique 241010XX PRNs, plus legacy cohort students for test continuity."""
    cse = departments["CSE"]

    # Module 1.1: Mandatory 4 named students + 1 pending student identity
    named_students_spec = [
        ("Ayan Mulani", "ayan.mulani@campus.edu", "STU24101", "01", "9823010001"),
        ("Arkam Momin", "arkam.momin@campus.edu", "STU24102", "02", "9823010002"),
        ("Piyush Mane", "piyush.mane@campus.edu", "STU24103", "03", "9823010003"),
        ("Ankush Saini", "ankush.saini@campus.edu", "STU24104", "04", "9823010004"),
        ("Student 5 (Pending Name)", "student5.pending@campus.edu", "STU24105", "05", "9823010005"),
    ]

    students = {}

    for name, email, code, roll_num, phone in named_students_spec:
        user = _get_or_create_user(email, name, "student", phone=phone)
        stu = Student.query.filter(
            db.or_(Student.user_id == user.id, Student.student_code == code)
        ).first()

        if not stu:
            # Module 1.2: All newly generated PRNs follow 241010XX
            prn = generate_unique_prn()
            stu = Student(
                user_id=user.id,
                student_code=code,
                department_id=cse.id,
                year_label="3rd Year",
                semester=6,
                division="A",
                roll_number=roll_num,
                prn=prn,
                status="active",
            )
            db.session.add(stu)
            db.session.flush()
        else:
            # Module 1.2: Never overwrite an existing student's PRN when rerunning seed
            existing_prn = stu.prn or generate_unique_prn()
            stu.user_id = user.id
            stu.department_id = cse.id
            stu.year_label = "3rd Year"
            stu.semester = 6
            stu.division = "A"
            stu.roll_number = roll_num
            stu.prn = existing_prn
            stu.status = "active"

        students[code] = stu

    # Legacy cohort students (student001 - student020) for automated test suite compatibility
    student_names = [
        "Aarav Sharma", "Aditi Deshmukh", "Akash Kulkarni", "Ananya Joshi",
        "Atharva Shinde", "Devika Nair", "Ishaan Patil", "Kavya Verma",
        "Manish Gupta", "Neha Rathod", "Omkar Pawar", "Pooja Chavan",
        "Pranav Kadam", "Riya Jadhav", "Rohan More", "Sakshi Sawant",
        "Siddharth Mehta", "Tanvi Salunkhe", "Varun Rane", "Yash Gaikwad"
    ]

    for i in range(1, 21):
        num_str = f"{i:03d}"
        roll_num = f"{i:02d}"
        code = f"STU2026{num_str}"
        email = f"student{num_str}@campus.edu"
        phone = f"982300{num_str:0>4}"
        name = student_names[i - 1]

        user = _get_or_create_user(email, name, "student", phone=phone)
        stu = Student.query.filter_by(student_code=code).first()
        if not stu:
            prn = f"PRN2026{num_str}"
            stu = Student(
                user_id=user.id,
                student_code=code,
                department_id=cse.id,
                year_label="3rd Year",
                semester=6,
                division="A",
                roll_number=roll_num,
                prn=prn,
                status="active",
            )
            db.session.add(stu)
            db.session.flush()
        else:
            stu.user_id = user.id
            stu.department_id = cse.id
            stu.year_label = "3rd Year"
            stu.semester = 6
            stu.division = "A"
            stu.roll_number = roll_num
            stu.status = "active"

        students[code] = stu

    db.session.commit()
    return students


def seed_courses(departments, faculty):
    """Provisions all Semester 6 CSE demonstration courses as per Module 3."""
    cse = departments["CSE"]
    courses_spec = [
        ("CS601", "Database Management Systems", 4, "core", 6, "CSE-301", 85, faculty["FAC2020021"].id),
        ("CS602", "Computer Networks", 4, "core", 6, "CSE-302", 80, faculty["FAC2019018"].id),
        ("CS603", "Design and Analysis of Algorithms", 4, "core", 6, "CSE-303", 75, faculty["FAC2023051"].id),
        ("CS604", "Software Engineering", 3, "core", 6, "CSE-304", 90, faculty["FAC2021034"].id),
        ("CS605", "Web Technology", 3, "core", 6, "CSE-305", 85, faculty["FAC2019018"].id),
        ("CS691", "Database Management Systems Laboratory", 2, "lab", 6, "CSE-LAB1", 80, faculty["FAC2022045"].id),
        ("CS692", "Computer Networks Laboratory", 2, "lab", 6, "CSE-LAB2", 75, faculty["FAC2019018"].id),
    ]

    courses = {}
    for code, title, credits, category, sem, room, cov, inst_id in courses_spec:
        c = Course.query.filter_by(code=code).first()
        if not c:
            c = Course(
                code=code,
                title=title,
                credits=credits,
                category=category,
                semester=sem,
                room=room,
                syllabus_coverage=cov,
                status="active",
                department_id=cse.id,
                instructor_id=inst_id,
            )
            db.session.add(c)
            db.session.flush()
        else:
            c.title = title
            c.credits = credits
            c.category = category
            c.semester = sem
            c.room = room
            c.syllabus_coverage = cov
            c.status = "active"
            c.department_id = cse.id
            c.instructor_id = inst_id
        courses[code] = c

    db.session.commit()
    return courses


def seed_faculty_assignments(faculty, courses, departments):
    """Links Faculty -> Course -> Year -> Semester -> Division."""
    cse = departments["CSE"]
    assignments_data = [
        (faculty["FAC2020021"].id, courses["CS601"].id, cse.id, "3rd Year", 6, "A"),
        (faculty["FAC2020021"].id, courses["CS601"].id, cse.id, "3rd Year", 6, "B"),
        (faculty["FAC2019018"].id, courses["CS602"].id, cse.id, "3rd Year", 6, "A"),
        (faculty["FAC2019018"].id, courses["CS602"].id, cse.id, "3rd Year", 6, "B"),
        (faculty["FAC2023051"].id, courses["CS603"].id, cse.id, "3rd Year", 6, "A"),
        (faculty["FAC2021034"].id, courses["CS604"].id, cse.id, "3rd Year", 6, "A"),
        (faculty["FAC2019018"].id, courses["CS605"].id, cse.id, "3rd Year", 6, "A"),
        (faculty["FAC2022045"].id, courses["CS691"].id, cse.id, "3rd Year", 6, "A"),
        (faculty["FAC2019018"].id, courses["CS692"].id, cse.id, "3rd Year", 6, "A"),
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
    db.session.commit()


def seed_enrollments(students, courses):
    """Enrolls all 20 students into all 6 courses."""
    for c_code, course in courses.items():
        for s_code, student in students.items():
            exists = Enrollment.query.filter_by(
                student_id=student.id, course_id=course.id
            ).first()
            if not exists:
                db.session.add(Enrollment(student_id=student.id, course_id=course.id))
    db.session.commit()


def seed_attendance(faculty, courses, students):
    """Creates realistic historical attendance sessions and records.
    CS601: 15 sessions (14 historical + 1 today marked)
    CS602: 14 sessions (today pending)
    CS603: 13 sessions (today pending)
    CS604: 12 sessions (11 historical + 1 today marked)
    CS691: 10 sessions (today pending)
    CS692: 10 sessions (today pending)"""
    session_plan = [
        ("CS601", faculty["FAC2020021"], 15, True),   # 15 sessions, marked today
        ("CS602", faculty["FAC2019018"], 14, False),  # 14 sessions, today pending
        ("CS603", faculty["FAC2023051"], 13, False),  # 13 sessions, today pending
        ("CS604", faculty["FAC2021034"], 12, True),   # 12 sessions, marked today
        ("CS691", faculty["FAC2022045"], 10, False),  # 10 sessions, today pending
        ("CS692", faculty["FAC2019018"], 10, False),  # 10 sessions, today pending
    ]

    # Student target attendance percentage benchmarks
    rates = [
        0.95, 0.91, 0.87, 0.84, 0.79, 0.74, 0.93, 0.81, 0.88, 0.76,
        0.94, 0.89, 0.82, 0.78, 0.90, 0.85, 0.77, 0.92, 0.83, 0.86,
    ]
    student_list = list(students.values())

    today = date.today()

    for c_code, fac, total_count, mark_today in session_plan:
        course = courses[c_code]

        # Calculate session dates
        session_dates = []
        if mark_today:
            session_dates.append(today)
            needed_past = total_count - 1
        else:
            needed_past = total_count

        cur_date = today - timedelta(days=1)
        count_past = 0
        while count_past < needed_past:
            # Skip Sundays
            if cur_date.weekday() != 6:
                session_dates.append(cur_date)
                count_past += 1
            cur_date -= timedelta(days=1)

        # Chronological order
        session_dates.sort()

        for s_idx, s_date in enumerate(session_dates):
            session = AttendanceSession.query.filter_by(
                course_id=course.id, session_date=s_date, division="A"
            ).first()
            if not session:
                session = AttendanceSession(
                    course_id=course.id,
                    marked_by_id=fac.id,
                    division="A",
                    session_date=s_date,
                )
                db.session.add(session)
                db.session.flush()

            for stu_idx, stu in enumerate(student_list):
                target_rate = rates[stu_idx % len(rates)]
                # Deterministic pseudo-random variation
                hash_val = ((s_idx + 1) * 31 + (stu.id * 17) + ord(c_code[2])) % 100
                if hash_val < int(target_rate * 100):
                    status = "late" if hash_val % 13 == 0 else "present"
                else:
                    status = "absent"

                rec = AttendanceRecord.query.filter_by(
                    session_id=session.id, student_id=stu.id
                ).first()
                if not rec:
                    rec = AttendanceRecord(
                        session_id=session.id,
                        student_id=stu.id,
                        status=status,
                    )
                    db.session.add(rec)
                else:
                    rec.status = status

    db.session.commit()


def seed_results(faculty, courses, students):
    """Generates realistic Result records for all 20 students across courses."""
    # Base performance distribution
    perf_data = [
        (26.5, 62.0), (25.0, 59.5), (24.0, 56.0), (23.5, 54.5), (21.5, 51.0),
        (20.0, 48.0), (26.0, 61.5), (22.5, 52.0), (24.5, 57.0), (20.5, 49.5),
        (27.0, 64.0), (25.5, 58.5), (23.0, 53.0), (21.0, 50.0), (25.0, 60.0),
        (24.0, 55.5), (20.5, 48.5), (26.5, 63.0), (23.0, 53.5), (24.5, 57.5),
    ]

    for c_idx, (c_code, course) in enumerate(courses.items()):
        inst_id = course.instructor_id
        for stu_idx, stu in enumerate(students.values()):
            base_int, base_end = perf_data[stu_idx % len(perf_data)]
            # Slight per-course variation (+/- 1.5)
            shift = ((c_idx + stu_idx) % 5) - 2
            internal = min(30.0, max(15.0, round(base_int + shift * 0.5, 1)))
            end_sem = min(70.0, max(35.0, round(base_end + shift * 1.0, 1)))

            res = Result.query.filter_by(student_id=stu.id, course_id=course.id).first()
            if not res:
                res = Result(
                    student_id=stu.id,
                    course_id=course.id,
                    entered_by_id=inst_id,
                    internal_marks=internal,
                    end_sem_marks=end_sem,
                    assessment_type="Semester Exam",
                    is_published=True,
                )
                db.session.add(res)
            else:
                res.internal_marks = internal
                res.end_sem_marks = end_sem
                res.entered_by_id = inst_id
                res.is_published = True

    db.session.commit()


def seed_assignments(faculty, courses, students):
    """Creates 4 coursework assignments with realistic student submissions."""
    now = datetime.now(timezone.utc)
    assignment_specs = [
        ("CS601", faculty["FAC2020021"], "Database Management Systems — Assignment 1",
         "Complete the normalization exercises from 1NF through BCNF. Provide SQL query execution plans.",
         now + timedelta(days=10), 10),
        ("CS602", faculty["FAC2019018"], "TCP/IP Socket Programming & Routing Assignment",
         "Implement a client-server multi-threaded chat architecture using socket APIs in C/Python.",
         now + timedelta(days=12), 10),
        ("CS603", faculty["FAC2023051"], "Algorithm Complexity & Dynamic Programming",
         "Analyze recurrence relations using Master Theorem and implement Bellman-Ford shortest path.",
         now + timedelta(days=14), 10),
        ("CS604", faculty["FAC2021034"], "Agile Sprint Planning & User Story Estimation",
         "Design a Jira-style Scrum backlog with story points, acceptance criteria, and burndown chart.",
         now + timedelta(days=16), 10),
    ]

    for c_code, fac, title, desc, due, pts in assignment_specs:
        course = courses[c_code]
        assign = Assignment.query.filter_by(title=title, course_id=course.id).first()
        if not assign:
            assign = Assignment(
                title=title,
                description=desc,
                course_id=course.id,
                faculty_id=fac.id,
                year_label="3rd Year",
                semester=6,
                division="A",
                due_date=due,
                total_points=pts,
            )
            db.session.add(assign)
            db.session.flush()
        else:
            assign.total_points = pts

        # For CS601, create realistic submissions: 12 submitted, 3 graded, 5 pending
        if c_code == "CS601":
            dummy_pdf = b"%PDF-1.4\\n1 0 obj << /Title (Assignment Solution) >> endobj\\ntrailer << /Root 1 0 R >>\\n%%EOF\\n"
            stu_list = list(students.values())
            for idx in range(min(15, len(stu_list))):
                stu = stu_list[idx]
                sub = AssignmentSubmission.query.filter_by(
                    assignment_id=assign.id, student_id=stu.id
                ).first()
                if not sub:
                    status = "graded" if idx < 3 else "submitted"
                    grade = 8.0 if idx == 0 else (9.0 if idx == 1 else 8.5) if idx < 3 else None
                    feedback = "Good work. Improve the explanation of normalization." if idx == 0 else ("Excellent schema design and 3NF normalization." if idx < 3 else None)
                    sub = AssignmentSubmission(
                        assignment_id=assign.id,
                        student_id=stu.id,
                        submission_text=f"Here is my completed submission for {title}. All requirements met.",
                        file_name=f"{stu.student_code}_Assignment1.pdf",
                        file_size_bytes=len(dummy_pdf),
                        file_data=dummy_pdf,
                        mime_type="application/pdf",
                        status=status,
                        grade=grade,
                        feedback=feedback,
                        graded_by_id=fac.id if status == "graded" else None,
                    )
                    db.session.add(sub)

    db.session.commit()


def seed_materials(faculty, courses, departments):
    """Provisions study materials for CS601, CS602, CS603, CS604 with persistent PDF storage."""
    cse = departments["CSE"]
    materials_spec = [
        ("CS601", faculty["FAC2020021"], "Module 1: Relational Algebra & SQL Normalization",
         "Comprehensive lecture notes covering functional dependencies, candidate keys, and BCNF.",
         "CS601_DBMS_Module1_Notes.pdf"),
        ("CS602", faculty["FAC2019018"], "Unit 2: Network Layer & IP Addressing Architecture",
         "Slide deck and tutorial guide on IPv4 CIDR subnetting, NAT, and link state routing.",
         "CS602_CNS_Unit2_Notes.pdf"),
        ("CS603", faculty["FAC2023051"], "Unit 3: Greedy Algorithms & Dynamic Programming",
         "Reference notes on Huffman coding, Fractional Knapsack, 0/1 Knapsack, and LCS problem.",
         "CS603_DAA_Unit3_Notes.pdf"),
        ("CS604", faculty["FAC2021034"], "Agile Methodologies & Scrum Framework Handbook",
         "Industry guide on sprint ceremonies, epic decomposition, and CI/CD development cycles.",
         "CS604_SE_Agile_Handbook.pdf"),
    ]

    sample_pdf_bytes = (
        b"%PDF-1.4\\n"
        b"%\\xe2\\xe3\\xcf\\xd3\\n"
        b"1 0 obj\\n<< /Type /Catalog /Pages 2 0 R >>\\nendobj\\n"
        b"2 0 obj\\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\\nendobj\\n"
        b"3 0 obj\\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>\\nendobj\\n"
        b"4 0 obj\\n<< /Length 75 >>\\nstream\\n"
        b"BT /F1 16 Tf 50 720 Td (Campus Connect ERP: Course Study Notes & Reference) Tj ET\\n"
        b"endstream\\nendobj\\n"
        b"xref\\n0 5\\n0000000000 65535 f \\n0000000015 00000 n \\n0000000068 00000 n \\n"
        b"0000000125 00000 n \\n0000000216 00000 n \\ntrailer\\n<< /Size 5 /Root 1 0 R >>\\n"
        b"startxref\\n340\\n%%EOF\\n"
    )

    for c_code, fac, title, desc, filename in materials_spec:
        course = courses[c_code]
        mat = StudyMaterial.query.filter_by(title=title, course_id=course.id).first()
        if not mat:
            mat = StudyMaterial(
                title=title,
                category="Notes",
                course_id=course.id,
                department_id=cse.id,
                year_label="3rd Year",
                semester=6,
                division="A",
                file_name=filename,
                file_size_bytes=len(sample_pdf_bytes),
                file_data=sample_pdf_bytes,
                file_path=None,
                mime_type="application/pdf",
                uploaded_by_id=fac.user_id,
            )
            db.session.add(mat)
        else:
            mat.uploaded_by_id = fac.user_id
            mat.file_name = filename
            mat.file_data = sample_pdf_bytes
            mat.file_size_bytes = len(sample_pdf_bytes)

    db.session.commit()


def seed_leave_requests(students, admin_user):
    """Provisions sample leave requests with Pending, Approved, and Rejected states."""
    stu_list = list(students.values())
    today = date.today()

    leaves_spec = [
        (stu_list[0], "Medical", today - timedelta(days=5), today - timedelta(days=3),
         "Severe viral flu and medical rest advised by physician.", "approved", "Medical certificate verified."),
        (stu_list[1], "Academic", today + timedelta(days=3), today + timedelta(days=5),
         "Representing college at Smart India Hackathon Regional Finals in Pune.", "pending", None),
        (stu_list[2], "Personal", today + timedelta(days=1), today + timedelta(days=3),
         "Attending family function out of station.", "rejected", "Cannot approve leave during mid-term examination week."),
    ]

    for stu, ltype, start_d, end_d, reason, status, remarks in leaves_spec:
        req = LeaveRequest.query.filter_by(student_id=stu.id, reason=reason).first()
        if not req:
            req = LeaveRequest(
                student_id=stu.id,
                leave_type=ltype,
                start_date=start_d,
                end_date=end_d,
                reason=reason,
                status=status,
                reviewed_by_id=admin_user.id if status != "pending" else None,
                review_remarks=remarks,
            )
            db.session.add(req)

    db.session.commit()


def seed_notices(admin_user, departments):
    """Provisions target notices for CSE Sem 6 Div A plus a general notice."""
    cse = departments["CSE"]
    notices_spec = [
        ("Internal Assessment-II Schedule (Odd Sem 2026-27)", "Academic",
         "Internal Assessment Test 2 for B.Tech CSE 3rd Year Semester 6 will commence from next Monday. Attendance is strictly compulsory.",
         cse.id, "3rd Year", 6, "A"),
        ("End Semester Examination Form Submission Notice", "Examination",
         "All CSE Semester 6 Division A students must submit exam verification forms along with clearance receipts to the exam cell.",
         cse.id, "3rd Year", 6, "A"),
        ("Mandatory Assignment Submission Deadline Reminder", "Academic",
         "CS601 (DBMS) and CS602 (Networks) coursework assignments must be uploaded to the portal before 11:59 PM next Friday.",
         cse.id, "3rd Year", 6, "A"),
        ("Campus Placement & Technical Internship Orientation", "Placement",
         "Training and Placement Cell (T&P) session on pre-placement interviews and algorithmic tests scheduled in Seminar Hall 1.",
         cse.id, "3rd Year", 6, "A"),
        ("National Smart Campus Hackathon 2026 Registration Open", "Event",
         "Teams of 4 from CSE Semester 6 are invited to register for the 36-hour National Hackathon before the registration deadline.",
         cse.id, "3rd Year", 6, "A"),
        ("Central Library Extended Hours During Mid-Term Examinations", "General",
         "The Central Library and Digital Reading Rooms will remain open until 11:00 PM on all working weekdays through the examination session.",
         None, None, None, "All"),
    ]

    for title, cat, body, dept_id, yr, sem, div in notices_spec:
        notice = Notice.query.filter_by(title=title).first()
        if not notice:
            notice = Notice(
                title=title,
                category=cat,
                body=body,
                department_id=dept_id,
                year_label=yr,
                semester=sem,
                division=div,
                posted_by_id=admin_user.id,
            )
            db.session.add(notice)

    db.session.commit()


def seed_events(admin_user):
    """Provisions campus events."""
    today = date.today()
    events_spec = [
        ("Annual Tech Fest - TechnoVision 2026",
         "Inter-college national tech fest featuring hackathons, paper presentations, and robotics arena.",
         "Technical", today + timedelta(days=18), "Main Campus Auditorium & Labs"),
        ("Inter-College 36-Hour Hackathon 2026",
         "Sprint innovation challenge focused on Smart City, EdTech, and Healthcare AI solutions.",
         "Technical", today + timedelta(days=25), "Advanced Computing Centre"),
        ("Core Technical Placement Preparation Workshop",
         "Hands-on workshop on system design, data structures, and mock technical interview rounds.",
         "Career", today + timedelta(days=8), "Seminar Hall B"),
        ("Algorithmic Coding Competition (CodeStorm 2026)",
         "Speed coding and algorithmic optimization contest hosted by the ACM Student Chapter.",
         "Technical", today + timedelta(days=14), "Computer Labs 1 & 2"),
    ]

    for title, desc, cat, edate, loc in events_spec:
        ev = Event.query.filter_by(title=title).first()
        if not ev:
            ev = Event(
                title=title,
                description=desc,
                category=cat,
                event_date=edate,
                location=loc,
                created_by_id=admin_user.id,
            )
            db.session.add(ev)

    db.session.commit()


def run_seed():
    print("Beginning database seed...")
    admin = ensure_default_admin()
    cleanup_old_demo_data()
    departments = seed_departments()
    faculty = seed_faculty(departments)
    students = seed_students(departments)
    courses = seed_courses(departments, faculty)
    seed_faculty_assignments(faculty, courses, departments)
    seed_enrollments(students, courses)
    seed_attendance(faculty, courses, students)
    seed_results(faculty, courses, students)
    seed_assignments(faculty, courses, students)
    seed_materials(faculty, courses, departments)
    seed_leave_requests(students, admin)
    seed_notices(admin, departments)
    seed_events(admin)

    # Calculate real database counts
    stu_count = Student.query.count()
    fac_count = Faculty.query.count()
    crs_count = Course.query.count()
    fa_count = FacultyAssignment.query.count()
    enr_count = Enrollment.query.count()
    sess_count = AttendanceSession.query.count()
    rec_count = AttendanceRecord.query.count()
    res_count = Result.query.count()
    asgn_count = Assignment.query.count()
    mat_count = StudyMaterial.query.count()
    not_count = Notice.query.count()
    ev_count = Event.query.count()
    leave_count = LeaveRequest.query.count()

    print("=" * 41)
    print(" CAMPUS CONNECT DEMO DATA READY")
    print("=" * 41)
    print("ADMIN")
    print("  Username: admin")
    print("  Password: admin")
    print()
    print("FACULTY")
    print("  1. Prof. Amit Deshmukh")
    print("     Email: amit.deshmukh@campus.edu")
    print("     Password: campus@123")
    print("     Course: CS601")
    print("     Division: A")
    print()
    print("  2. Prof. Rajesh Verma")
    print("     Email: rajesh.verma@campus.edu")
    print("     Password: campus@123")
    print("     Course: CS602")
    print("     Division: A")
    print()
    print("  3. Prof. Neha Patil")
    print("     Email: neha.patil@campus.edu")
    print("     Password: campus@123")
    print("     Course: CS604")
    print("     Division: A")
    print()
    print("  4. Prof. Pooja More")
    print("     Email: pooja.more@campus.edu")
    print("     Password: campus@123")
    print("     Course: CS691")
    print("     Division: A")
    print()
    print("  5. Prof. Snehal Kulkarni")
    print("     Email: snehal.kulkarni@campus.edu")
    print("     Password: campus@123")
    print("     Course: CS603")
    print("     Division: A")
    print()
    print(f"STUDENTS: {stu_count}")
    print(f"COURSES: {crs_count}")
    print(f"FACULTY ASSIGNMENTS: {fa_count}")
    print(f"ENROLLMENTS: {enr_count}")
    print(f"ATTENDANCE SESSIONS: {sess_count}")
    print(f"ATTENDANCE RECORDS: {rec_count}")
    print(f"RESULTS: {res_count}")
    print(f"ASSIGNMENTS: {asgn_count}")
    print(f"STUDY MATERIALS: {mat_count}")
    print(f"NOTICES: {not_count}")
    print(f"EVENTS: {ev_count}")
    print(f"LEAVE REQUESTS: {leave_count}")
    print("=" * 41)


if __name__ == "__main__":
    from app import create_app
    app = create_app()
    with app.app_context():
        run_seed()
