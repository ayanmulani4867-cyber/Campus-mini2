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


def generate_unique_prn(allocated_in_run=None):
    """Generates a unique student PRN adhering to format 241010XX (prefix 241010 + 2 decimal digits 00-99).
    Enforces uniqueness at database level and rejects duplicates.
    Checks for PRN exhaustion across the 100-value pool."""
    import random
    
    # Query all existing 241010XX PRNs currently in database
    existing_records = db.session.query(Student.prn, Student.student_code).all()
    used_suffixes = set()
    for prn, code in existing_records:
        for val in (prn, code):
            if val and str(val).startswith("241010") and len(str(val)) == 8 and str(val)[6:].isdigit():
                used_suffixes.add(int(str(val)[6:]))
                
    if allocated_in_run:
        used_suffixes.update(allocated_in_run)

    available_suffixes = [i for i in range(100) if i not in used_suffixes]
    
    if not available_suffixes:
        raise RuntimeError(
            "PRN Exhaustion: All 100 possible PRN values in the '241010XX' format (24101000 - 24101099) "
            "are currently allocated in the database."
        )

    # Randomly select from available decimal suffixes
    chosen_suffix = random.choice(available_suffixes)
    candidate = f"241010{chosen_suffix:02d}"
    
    if allocated_in_run is not None:
        allocated_in_run.add(chosen_suffix)
        
    return candidate


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
    """Safely cleans obsolete prohibited legacy faculty records while preserving legitimate department faculty."""
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
    """Provisions primary demonstration faculty accounts across all configured departments."""
    cse = departments["CSE"]
    ece = departments["ECE"]
    mech = departments["MECH"]
    ce = departments["CE"]

    faculty_spec = [
        ("amit.deshmukh@campus.edu", "Prof. Amit Deshmukh", "FAC2020021", "Associate Professor", "9820000001", cse.id),
        ("rajesh.verma@campus.edu", "Prof. Rajesh Verma", "FAC2019018", "Professor & Head", "9820000002", cse.id),
        ("neha.patil@campus.edu", "Prof. Neha Patil", "FAC2021034", "Assistant Professor", "9820000003", cse.id),
        ("pooja.more@campus.edu", "Prof. Pooja More", "FAC2022045", "Assistant Professor", "9820000004", cse.id),
        ("snehal.kulkarni@campus.edu", "Prof. Snehal Kulkarni", "FAC2023051", "Assistant Professor", "9820000005", cse.id),
        ("prof.mech@campus.edu", "Prof Test Mechanical Engineering", "FAC2026006", "Assistant Professor", "9123456781", mech.id),
        ("prof.civil@campus.edu", "Prof Test Civil Engineering", "FAC2026007", "Assistant Professor", "9123456782", ce.id),
        ("prof.ece@campus.edu", "Prof Test Electronics & Communication", "FAC2026008", "Assistant Professor", "9123456783", ece.id),
    ]
    faculty_map = {}
    for email, name, code, designation, phone, dept_id in faculty_spec:
        user = _get_or_create_user(email, name, "faculty", phone=phone)
        fac = Faculty.query.filter(
            db.or_(Faculty.faculty_code == code, Faculty.user_id == user.id)
        ).first()
        if not fac:
            fac = Faculty(
                user_id=user.id,
                faculty_code=code,
                department_id=dept_id,
                designation=designation,
                status="active",
            )
            db.session.add(fac)
            db.session.flush()
        else:
            fac.user_id = user.id
            fac.department_id = dept_id
            fac.designation = designation
            fac.status = "active"
        faculty_map[code] = fac

    db.session.commit()
    return faculty_map


def seed_courses(departments, faculty):
    """Provisions all demonstration courses across departments as configured."""
    cse = departments["CSE"]
    ece = departments["ECE"]
    mech = departments["MECH"]
    ce = departments["CE"]

    courses_spec = [
        # (code, title, credits, category, sem, room, cov, instructor_key, dept_id)
        ("CS601", "Database Management Systems", 4, "core", 6, "CSE-301", 85, "FAC2020021", cse.id),
        ("CS602", "Computer Networks", 4, "core", 6, "CSE-302", 80, "FAC2019018", cse.id),
        ("CS603", "Design and Analysis of Algorithms", 4, "core", 6, "CSE-303", 75, "FAC2023051", cse.id),
        ("CS604", "Software Engineering", 3, "core", 6, "CSE-304", 90, "FAC2021034", cse.id),
        ("CS605", "Web Technology", 3, "core", 6, "CSE-305", 85, "FAC2019018", cse.id),
        ("CS691", "Database Management Systems Laboratory", 2, "lab", 6, "CSE-LAB1", 80, "FAC2022045", cse.id),
        ("CS692", "Computer Networks Laboratory", 2, "lab", 6, "CSE-LAB2", 75, "FAC2019018", cse.id),
        ("CS501", "Operating Systems", 4, "core", 5, "CSE-201", 80, "FAC2021034", cse.id),
        ("ME301", "Thermodynamics & Heat Transfer", 4, "core", 5, "MECH-101", 75, "FAC2026006", mech.id),
        ("ME401", "Power Plant Engineering", 4, "core", 8, "MECH-201", 70, "FAC2026006", mech.id),
        ("EC301", "Digital Signal Processing", 4, "core", 5, "ECE-101", 80, "FAC2026008", ece.id),
        ("EC201", "Analog Electronic Circuits", 4, "core", 4, "ECE-201", 75, "FAC2026008", ece.id),
        ("CE301", "Structural Analysis", 4, "core", 5, "CE-101", 75, "FAC2026007", ce.id),
    ]

    courses = {}
    for code, title, credits, category, sem, room, cov, inst_code, dept_id in courses_spec:
        c = Course.query.filter_by(code=code).first()
        inst_id = faculty[inst_code].id if inst_code in faculty else None
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
                department_id=dept_id,
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
            c.department_id = dept_id
            if inst_id:
                c.instructor_id = inst_id
        courses[code] = c

    db.session.commit()
    return courses


def seed_faculty_assignments(faculty, courses, departments):
    """Links Faculty -> Course -> Year -> Semester -> Division.
    Maintains strict RBAC isolation: Prof. Amit Deshmukh (FAC2020021) teaches ONLY CS601 Div A."""
    cse = departments["CSE"]
    ece = departments["ECE"]
    mech = departments["MECH"]
    ce = departments["CE"]

    # First clean any invalid assignment where Amit Deshmukh is assigned to CS601 Div B
    bad_fa = FacultyAssignment.query.filter_by(
        faculty_id=faculty["FAC2020021"].id,
        course_id=courses["CS601"].id,
        division="B"
    ).first()
    if bad_fa:
        db.session.delete(bad_fa)
        db.session.commit()

    assignments_data = [
        # CSE Semester 6 Division A
        (faculty["FAC2020021"].id, courses["CS601"].id, cse.id, "3rd Year", 6, "A"),
        (faculty["FAC2019018"].id, courses["CS602"].id, cse.id, "3rd Year", 6, "A"),
        (faculty["FAC2023051"].id, courses["CS603"].id, cse.id, "3rd Year", 6, "A"),
        (faculty["FAC2021034"].id, courses["CS604"].id, cse.id, "3rd Year", 6, "A"),
        (faculty["FAC2019018"].id, courses["CS605"].id, cse.id, "3rd Year", 6, "A"),
        (faculty["FAC2022045"].id, courses["CS691"].id, cse.id, "3rd Year", 6, "A"),
        (faculty["FAC2019018"].id, courses["CS692"].id, cse.id, "3rd Year", 6, "A"),

        # CSE Semester 6 Division B (Assigned to Prof. Rajesh Verma & peers, NOT Prof. Amit Deshmukh)
        (faculty["FAC2019018"].id, courses["CS601"].id, cse.id, "3rd Year", 6, "B"),
        (faculty["FAC2019018"].id, courses["CS602"].id, cse.id, "3rd Year", 6, "B"),
        (faculty["FAC2023051"].id, courses["CS603"].id, cse.id, "3rd Year", 6, "B"),
        (faculty["FAC2021034"].id, courses["CS604"].id, cse.id, "3rd Year", 6, "B"),
        (faculty["FAC2019018"].id, courses["CS605"].id, cse.id, "3rd Year", 6, "B"),
        (faculty["FAC2022045"].id, courses["CS691"].id, cse.id, "3rd Year", 6, "B"),
        (faculty["FAC2019018"].id, courses["CS692"].id, cse.id, "3rd Year", 6, "B"),

        # CSE Semester 5 Divisions A & B
        (faculty["FAC2021034"].id, courses["CS501"].id, cse.id, "3rd Year", 5, "A"),
        (faculty["FAC2021034"].id, courses["CS501"].id, cse.id, "3rd Year", 5, "B"),

        # MECH Semester 5 Division A & Semester 8 Division A
        (faculty["FAC2026006"].id, courses["ME301"].id, mech.id, "3rd Year", 5, "A"),
        (faculty["FAC2026006"].id, courses["ME401"].id, mech.id, "4th Year", 8, "A"),

        # ECE Semester 5 Division A & Semester 4 Division B
        (faculty["FAC2026008"].id, courses["EC301"].id, ece.id, "3rd Year", 5, "A"),
        (faculty["FAC2026008"].id, courses["EC201"].id, ece.id, "2nd Year", 4, "B"),

        # CE Semester 5 Division A
        (faculty["FAC2026007"].id, courses["CE301"].id, ce.id, "3rd Year", 5, "A"),
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


def seed_students(departments):
    """Provisions realistic student records across all configured academic divisions.
    1. Preserves mandatory Module 1 students:
       Ayan Mulani, Arkam Momin, Piyush Mane, Ankush Saini (retaining existing PRNs and rolls)
    2. Preserves legacy cohort students (student001 - student020) and any existing genuine students.
    3. Populates every configured division to reach 10 active student records.
    4. Clearly labels generated records as demonstration data.
    5. Newly generated PRNs strictly adhere to format 241010XX with uniqueness enforced."""
    cse = departments["CSE"]
    allocated_prns = set()

    # Track already used PRNs
    for p in db.session.query(Student.prn).all():
        if p[0] and p[0].startswith("241010") and len(p[0]) == 8 and p[0][6:].isdigit():
            allocated_prns.add(int(p[0][6:]))

    # Module 1.1: Mandatory named students in CSE Sem 6 Div A
    named_students_spec = [
        ("Ayan Mulani", "ayan.mulani@campus.edu", "STU24101", "01", "9823010001", "24101026"),
        ("Arkam Momin", "arkam.momin@campus.edu", "STU24102", "02", "9823010002", "24101035"),
        ("Piyush Mane", "piyush.mane@campus.edu", "STU24103", "03", "9823010003", "24101092"),
        ("Ankush Saini", "ankush.saini@campus.edu", "STU24104", "04", "9823010004", "24101006"),
        ("Student 5 (Pending Name)", "student5.pending@campus.edu", "STU24105", "05", "9823010005", None),
    ]

    students = {}

    for name, email, code, roll_num, phone, expected_prn in named_students_spec:
        user = _get_or_create_user(email, name, "student", phone=phone)
        stu = Student.query.filter(
            db.or_(Student.user_id == user.id, Student.student_code == code)
        ).first()

        if not stu:
            prn = expected_prn if expected_prn else generate_unique_prn(allocated_prns)
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
            existing_prn = stu.prn or expected_prn or generate_unique_prn(allocated_prns)
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

    # SECTION 3: TOP UP EVERY CONFIGURED DIVISION TO AT LEAST 10 STUDENTS
    configured_divisions = [
        ("CSE", 6, "A", "3rd Year"),
        ("CSE", 6, "B", "3rd Year"),
        ("CSE", 5, "A", "3rd Year"),
        ("CSE", 5, "B", "3rd Year"),
        ("ECE", 5, "A", "3rd Year"),
        ("ECE", 4, "B", "2nd Year"),
        ("MECH", 5, "A", "3rd Year"),
        ("MECH", 8, "A", "4th Year"),
        ("CE", 5, "A", "3rd Year"),
    ]

    for dept_code, sem, div, yr_label in configured_divisions:
        dept = departments[dept_code]
        existing_students = Student.query.filter_by(
            department_id=dept.id, semester=sem, division=div
        ).all()
        
        current_count = len(existing_students)
        # If division already has 10 or more genuine students, preserve them all intact
        if current_count >= 10:
            continue

        needed = 10 - current_count
        taken_rolls = {s.roll_number for s in existing_students if s.roll_number}

        for _ in range(needed):
            # Select lowest available roll number 01-99
            roll_candidate = None
            for r in range(1, 100):
                r_str = f"{r:02d}"
                if r_str not in taken_rolls:
                    roll_candidate = r_str
                    taken_rolls.add(r_str)
                    break

            if not roll_candidate:
                roll_candidate = f"{len(taken_rolls)+1:02d}"

            prn = generate_unique_prn(allocated_prns)
            code = f"DEMO_{dept_code}{sem}{div}_{roll_candidate}"
            name = f"Demo Student {dept_code}-{sem}{div} Roll-{roll_candidate}"
            email = f"demo.{dept_code.lower()}{sem}{div.lower()}.{roll_candidate}@campus.edu"
            phone = f"987{sem}{int(roll_candidate):06d}"

            user = _get_or_create_user(email, name, "student", phone=phone)
            stu = Student.query.filter_by(student_code=code).first()
            if not stu:
                stu = Student(
                    user_id=user.id,
                    student_code=code,
                    department_id=dept.id,
                    year_label=yr_label,
                    semester=sem,
                    division=div,
                    roll_number=roll_candidate,
                    prn=prn,
                    status="active",
                )
                db.session.add(stu)
                db.session.flush()
            else:
                stu.user_id = user.id
                stu.department_id = dept.id
                stu.year_label = yr_label
                stu.semester = sem
                stu.division = div
                stu.roll_number = roll_candidate
                stu.status = "active"

            students[code] = stu

    db.session.commit()
    return students


def seed_enrollments(departments, courses):
    """Enrolls every active student in all courses matching their department and semester."""
    all_students = Student.query.filter_by(status="active").all()
    enrolled_count = 0
    for stu in all_students:
        dept_courses = Course.query.filter_by(
            department_id=stu.department_id, semester=stu.semester
        ).all()
        for c in dept_courses:
            exists = Enrollment.query.filter_by(
                student_id=stu.id, course_id=c.id
            ).first()
            if not exists:
                db.session.add(Enrollment(student_id=stu.id, course_id=c.id))
                enrolled_count += 1
    db.session.commit()
    return enrolled_count


def seed_attendance(faculty, courses, students):
    """Creates realistic historical attendance sessions and records across populated divisions.
    Preserves existing genuine attendance records. Labeled clearly as sample data."""
    # 1. CSE Semester 6 Division A (Full historical attendance plan)
    session_plan = [
        ("CS601", faculty["FAC2020021"], 15, True, "A"),
        ("CS602", faculty["FAC2019018"], 14, False, "A"),
        ("CS603", faculty["FAC2023051"], 13, False, "A"),
        ("CS604", faculty["FAC2021034"], 12, True, "A"),
        ("CS691", faculty["FAC2022045"], 10, False, "A"),
        ("CS692", faculty["FAC2019018"], 10, False, "A"),
    ]

    rates = [
        0.95, 0.91, 0.87, 0.84, 0.79, 0.74, 0.93, 0.81, 0.88, 0.76,
        0.94, 0.89, 0.82, 0.78, 0.90, 0.85, 0.77, 0.92, 0.83, 0.86,
    ]
    
    div_a_students = Student.query.filter_by(division="A", semester=6).all()
    today = date.today()

    for c_code, fac, total_count, mark_today, div in session_plan:
        if c_code not in courses:
            continue
        course = courses[c_code]

        session_dates = []
        if mark_today:
            session_dates.append(today)
            needed_past = total_count - 1
        else:
            needed_past = total_count

        cur_date = today - timedelta(days=1)
        count_past = 0
        while count_past < needed_past:
            if cur_date.weekday() != 6:
                session_dates.append(cur_date)
                count_past += 1
            cur_date -= timedelta(days=1)

        session_dates.sort()

        for s_idx, s_date in enumerate(session_dates):
            session = AttendanceSession.query.filter_by(
                course_id=course.id, session_date=s_date, division=div
            ).first()
            if not session:
                session = AttendanceSession(
                    course_id=course.id,
                    marked_by_id=fac.id,
                    division=div,
                    session_date=s_date,
                )
                db.session.add(session)
                db.session.flush()

            for stu_idx, stu in enumerate(div_a_students):
                target_rate = rates[stu_idx % len(rates)]
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

    # 2. Sample demonstration attendance sessions for ALL other divisions
    sample_div_plans = [
        ("CS601", faculty["FAC2019018"], "B", 6, 1),
        ("CS602", faculty["FAC2019018"], "B", 6, 1),
        ("CS501", faculty["FAC2021034"], "A", 5, 1),
        ("CS501", faculty["FAC2021034"], "B", 5, 1),
        ("ME301", faculty["FAC2026006"], "A", 5, 1),
        ("ME401", faculty["FAC2026006"], "A", 8, 1),
        ("EC301", faculty["FAC2026008"], "A", 5, 1),
        ("EC201", faculty["FAC2026008"], "B", 4, 1),
        ("CE301", faculty["FAC2026007"], "A", 5, 1),
    ]

    for c_code, fac, div, sem, _ in sample_div_plans:
        if c_code not in courses:
            continue
        course = courses[c_code]
        div_stus = Student.query.filter_by(
            department_id=course.department_id, semester=sem, division=div
        ).all()

        session = AttendanceSession.query.filter_by(
            course_id=course.id, session_date=today, division=div
        ).first()
        if not session:
            session = AttendanceSession(
                course_id=course.id,
                marked_by_id=fac.id,
                division=div,
                session_date=today,
            )
            db.session.add(session)
            db.session.flush()

        for stu_idx, stu in enumerate(div_stus):
            status = "present" if stu_idx % 4 != 0 else ("late" if stu_idx % 2 == 0 else "absent")
            rec = AttendanceRecord.query.filter_by(
                session_id=session.id, student_id=stu.id
            ).first()
            if not rec:
                db.session.add(AttendanceRecord(
                    session_id=session.id,
                    student_id=stu.id,
                    status=status
                ))

    db.session.commit()


def seed_results(faculty, courses, students):
    """Generates realistic demonstration Result records across courses."""
    perf_data = [
        (26.5, 62.0), (25.0, 59.5), (24.0, 56.0), (23.5, 54.5), (21.5, 51.0),
        (20.0, 48.0), (26.0, 61.5), (22.5, 52.0), (24.5, 57.0), (20.5, 49.5),
        (27.0, 64.0), (25.5, 58.5), (23.0, 53.0), (21.0, 50.0), (25.0, 60.0),
        (24.0, 55.5), (20.5, 48.5), (26.5, 63.0), (23.0, 53.5), (24.5, 57.5),
    ]

    for c_idx, (c_code, course) in enumerate(courses.items()):
        inst_id = course.instructor_id
        enrolled_stus = Student.query.join(
            Enrollment, Student.id == Enrollment.student_id
        ).filter(Enrollment.course_id == course.id).all()

        for stu_idx, stu in enumerate(enrolled_stus):
            base_int, base_end = perf_data[stu_idx % len(perf_data)]
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
                if inst_id:
                    res.entered_by_id = inst_id
                res.is_published = True

    db.session.commit()


def seed_assignments(faculty, courses, students):
    """Creates coursework assignments with realistic student submissions evaluated between 0 and 10 marks."""
    now = datetime.now(timezone.utc)
    assignment_specs = [
        ("CS601", faculty["FAC2020021"], "Database Management Systems — Assignment 1",
         "Complete the normalization exercises from 1NF through BCNF. Provide SQL query execution plans.",
         now + timedelta(days=10), 10, "All"),
        ("CS602", faculty["FAC2019018"], "TCP/IP Socket Programming & Routing Assignment",
         "Implement a client-server multi-threaded chat architecture using socket APIs in C/Python.",
         now + timedelta(days=12), 10, "All"),
        ("CS603", faculty["FAC2023051"], "Algorithm Complexity & Dynamic Programming",
         "Analyze recurrence relations using Master Theorem and implement Bellman-Ford shortest path.",
         now + timedelta(days=14), 10, "All"),
        ("CS604", faculty["FAC2021034"], "Agile Sprint Planning & User Story Estimation",
         "Design a Jira-style Scrum backlog with story points, acceptance criteria, and burndown chart.",
         now + timedelta(days=16), 10, "All"),
        ("CS501", faculty["FAC2021034"], "Operating Systems Process Synchronization Problem Set",
         "Implement Producer-Consumer problem using Semaphores and Mutex in POSIX threads.",
         now + timedelta(days=10), 10, "All"),
        ("ME301", faculty["FAC2026006"], "Thermodynamic Heat Cycle Analysis Assignment",
         "Calculate Rankine cycle thermal efficiency and heat loss under varying pressure states.",
         now + timedelta(days=12), 10, "All"),
        ("EC301", faculty["FAC2026008"], "DSP Digital Filter Design & FFT Implementation",
         "Design a Butterworth low-pass IIR filter using bilinear transformation in MATLAB/Python.",
         now + timedelta(days=14), 10, "All"),
        ("CE301", faculty["FAC2026007"], "Structural Analysis Moment Distribution Method",
         "Solve indeterminate continuous beam bending moments using Hardy Cross moment distribution.",
         now + timedelta(days=15), 10, "All"),
    ]

    dummy_pdf = b"%PDF-1.4\n1 0 obj << /Title (Assignment Solution Demo) >> endobj\ntrailer << /Root 1 0 R >>\n%%EOF\n"

    for c_code, fac, title, desc, due, pts, div in assignment_specs:
        if c_code not in courses:
            continue
        course = courses[c_code]
        assign = Assignment.query.filter_by(title=title, course_id=course.id).first()
        if not assign:
            assign = Assignment(
                title=title,
                description=desc,
                course_id=course.id,
                faculty_id=fac.id,
                year_label="3rd Year",
                semester=course.semester,
                division=div,
                due_date=due,
                total_points=pts,
            )
            db.session.add(assign)
            db.session.flush()
        else:
            assign.total_points = pts
            assign.division = div

        # Seed sample submissions for enrolled students
        enrolled_stus = Student.query.join(
            Enrollment, Student.id == Enrollment.student_id
        ).filter(Enrollment.course_id == course.id).all()

        for idx, stu in enumerate(enrolled_stus[:12]):
            sub = AssignmentSubmission.query.filter_by(
                assignment_id=assign.id, student_id=stu.id
            ).first()
            if not sub:
                status = "graded" if idx < 3 else "submitted"
                grade = 8.0 if idx == 0 else (9.0 if idx == 1 else 8.5) if idx < 3 else None
                feedback = (
                    "Sample Evaluation: Good work. Clear derivation of solution." if idx == 0
                    else ("Sample Evaluation: Excellent work meeting all coursework rubric criteria." if idx < 3 else None)
                )
                sub = AssignmentSubmission(
                    assignment_id=assign.id,
                    student_id=stu.id,
                    submission_text=f"Sample demonstration submission for {title}.",
                    file_name=f"{stu.student_code}_Solution.pdf",
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
    """Provisions study materials with persistent PDF storage."""
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
        b"%PDF-1.4\n"
        b"%\xe2\xe3\xcf\xd3\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>\nendobj\n"
        b"4 0 obj\n<< /Length 75 >>\nstream\n"
        b"BT /F1 16 Tf 50 720 Td (Campus Connect ERP: Course Study Notes & Reference) Tj ET\n"
        b"endstream\nendobj\n"
        b"xref\n0 5\n0000000000 65535 f \n0000000015 00000 n \n0000000068 00000 n \n"
        b"0000000125 00000 n \n0000000216 00000 n \ntrailer\n<< /Size 5 /Root 1 0 R >>\n"
        b"startxref\n340\n%%EOF\n"
    )

    for c_code, fac, title, desc, filename in materials_spec:
        if c_code not in courses:
            continue
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
                division="All",
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
    if not stu_list:
        return
    today = date.today()

    leaves_spec = [
        (stu_list[0], "Medical", today - timedelta(days=5), today - timedelta(days=3),
         "Severe viral flu and medical rest advised by physician.", "approved", "Medical certificate verified."),
        (stu_list[1] if len(stu_list) > 1 else stu_list[0], "Academic", today + timedelta(days=3), today + timedelta(days=5),
         "Representing college at Smart India Hackathon Regional Finals in Pune.", "pending", None),
        (stu_list[2] if len(stu_list) > 2 else stu_list[0], "Personal", today + timedelta(days=1), today + timedelta(days=3),
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
    """Provisions target notices across divisions plus general institutional notices."""
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
         cse.id, "3rd Year", 6, "All"),
        ("Campus Placement & Technical Internship Orientation", "Placement",
         "Training and Placement Cell (T&P) session on pre-placement interviews and algorithmic tests scheduled in Seminar Hall 1.",
         cse.id, "3rd Year", 6, "All"),
        ("National Smart Campus Hackathon 2026 Registration Open", "Event",
         "Teams of 4 from all engineering departments are invited to register for the 36-hour National Hackathon before deadline.",
         None, None, None, "All"),
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


def cleanup_all_students_and_faculty():
    """Safely and transactionally removes all student and faculty records and all dependent
    attendance, enrollment, submission, assignment, and result records while strictly preserving
    the admin account, academic departments, courses, notices, and events."""
    from sqlalchemy import text
    admin = ensure_default_admin()

    # 1. Clear course instructor links
    db.session.execute(text("UPDATE courses SET instructor_id = NULL;"))

    # 2. Reassign study materials to admin so course notes library is preserved
    db.session.execute(
        text("UPDATE study_materials SET uploaded_by_id = :aid;"),
        {"aid": admin.id}
    )

    # 3. Delete student & faculty dependent records in topological FK order
    db.session.execute(text("DELETE FROM assignment_submissions;"))
    db.session.execute(text("DELETE FROM assignments;"))
    db.session.execute(text("DELETE FROM attendance_records;"))
    db.session.execute(text("DELETE FROM attendance_sessions;"))
    db.session.execute(text("DELETE FROM results;"))
    db.session.execute(text("DELETE FROM leave_requests;"))
    db.session.execute(text("DELETE FROM enrollments;"))
    db.session.execute(text("DELETE FROM faculty_assignments;"))

    # 4. Delete Students & Faculty profile tables
    db.session.execute(text("DELETE FROM students;"))
    db.session.execute(text("DELETE FROM faculty;"))

    # 5. Delete UserSessions for student and faculty users
    db.session.execute(text(
        "DELETE FROM user_sessions WHERE user_id IN (SELECT id FROM users WHERE role IN ('student', 'faculty'));"
    ))

    # 6. Delete User accounts for students and faculty
    db.session.execute(text("DELETE FROM users WHERE role IN ('student', 'faculty');"))

    db.session.commit()
    print("All existing student and faculty records successfully removed from database.")


def run_seed(populate=False):
    print("Beginning database seed...")
    admin = ensure_default_admin()
    cleanup_old_demo_data()
    departments = seed_departments()
    courses = seed_courses(departments, {})
    seed_notices(admin, departments)
    seed_events(admin)

    if not populate:
        print("Database initialized: Admin account, departments, and courses preserved.")
        print("Note: Student and faculty accounts were NOT seeded (populate=False).")
        return

    faculty = seed_faculty(departments)
    courses = seed_courses(departments, faculty)
    seed_faculty_assignments(faculty, courses, departments)
    students = seed_students(departments)
    enrolled_count = seed_enrollments(departments, courses)
    seed_attendance(faculty, courses, students)
    seed_results(faculty, courses, students)
    seed_assignments(faculty, courses, students)
    seed_materials(faculty, courses, departments)
    seed_leave_requests(students, admin)

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

    # PRN Pool capacity stats
    all_prns = [s.prn for s in Student.query.all() if s.prn]
    prn_24_count = sum(1 for p in all_prns if p.startswith("241010") and len(p) == 8 and p[6:].isdigit())
    remaining_prns = 100 - prn_24_count

    print("=" * 60)
    print(" CAMPUS CONNECT ERP -- ALL SECTIONS POPULATED (10+ STUDENTS)")
    print("=" * 60)
    print("ADMIN CREDENTIALS")
    print("  Username: admin")
    print("  Password: admin")
    print()
    print("DEPARTMENT & SECTION BREAKDOWN:")
    div_breakdown = (
        db.session.query(
            Department.code, Student.semester, Student.division, db.func.count(Student.id)
        )
        .join(Department, Student.department_id == Department.id)
        .group_by(Department.code, Student.semester, Student.division)
        .order_by(Department.code, Student.semester, Student.division)
        .all()
    )
    for d_code, sem, div, cnt in div_breakdown:
        print(f"  * {d_code} Semester {sem} Division {div}: {cnt} active students")

    print()
    print(f"TOTAL STUDENTS: {stu_count}")
    print(f"TOTAL COURSES: {crs_count}")
    print(f"FACULTY ASSIGNMENTS: {fa_count}")
    print(f"COURSE ENROLLMENTS: {enr_count}")
    print(f"ATTENDANCE SESSIONS: {sess_count}")
    print(f"ATTENDANCE RECORDS: {rec_count}")
    print(f"RESULTS: {res_count}")
    print(f"ASSIGNMENTS: {asgn_count}")
    print(f"PRN FORMAT '241010XX' IN USE: {prn_24_count} / 100 (Remaining Pool: {remaining_prns})")
    print("=" * 60)


if __name__ == "__main__":
    import sys
    from app import create_app
    app = create_app()
    with app.app_context():
        if "--cleanup" in sys.argv:
            cleanup_all_students_and_faculty()
        elif "--populate" in sys.argv:
            run_seed(populate=True)
        else:
            run_seed(populate=False)
