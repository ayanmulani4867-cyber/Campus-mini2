from flask import Blueprint, request, jsonify
from extensions import db
from models import Student, User, Department
from utils.auth import roles_required, login_required, current_user
from utils.validators import require_fields, validate_email, validate_phone, ValidationError

bp = Blueprint("students", __name__, url_prefix="/api/students")

DEFAULT_PASSWORD = None  # New member password is their phone number.


def generate_unique_prn(max_attempts=300):
    """Generates a unique student PRN adhering to format 241010XX (prefix 241010 + 2 decimal digits 00-99).
    Enforces uniqueness across all existing students in the database."""
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

    raise ValidationError("All 100 PRNs in the 241010XX pool have been allocated.")


@bp.get("/generate-prn")
@roles_required("admin")
def get_generated_prn():
    """Generates a fresh unique 241010XX PRN for the admin creation modal."""
    prn = generate_unique_prn()
    return jsonify({"success": True, "prn": prn, "data": {"prn": prn}})


@bp.get("")
@roles_required("admin")
def list_students():
    """User Directory student list is restricted to Administrators."""
    q = Student.query
    search = request.args.get("q")
    if search:
        like = f"%{search}%"
        q = q.join(User).filter(
            db.or_(User.full_name.ilike(like), Student.student_code.ilike(like), Student.prn.ilike(like))
        )
    students = q.all()
    return jsonify({"success": True, "data": [s.to_dict() for s in students]})


@bp.get("/<string:student_code>")
@login_required
def get_student(student_code):
    user = current_user()
    student = Student.query.filter(
        db.or_(Student.student_code == student_code, Student.prn == student_code)
    ).first()
    if not student:
        return jsonify({"success": False, "error": "Student not found."}), 404
    if user.role == "student" and user.student_profile.id != student.id:
        return jsonify({"success": False, "error": "Forbidden: cannot view other student profiles."}), 403
    return jsonify({"success": True, "data": student.to_dict()})


@bp.post("")
@roles_required("admin")
def create_student():
    from sqlalchemy.exc import IntegrityError
    data = request.get_json(silent=True) or {}
    require_fields(data, ["name", "email", "department"])

    email = validate_email(data["email"])
    raw_phone = data.get("phone")
    phone = validate_phone(str(raw_phone).strip()) if raw_phone else None
    initial_password = str(raw_phone).strip() if (raw_phone and len(str(raw_phone).strip()) >= 6) else "campus@123"
    if User.query.filter_by(email=email).first():
        raise ValidationError("A user with that email already exists.")

    dept = Department.resolve(data["department"])
    if not dept:
        raise ValidationError(f"Unknown department: {data['department']}")

    # Academic year and semester
    year = data.get("year", "3rd Year").strip()
    try:
        semester = int(data.get("semester", 6))
    except (ValueError, TypeError):
        semester = 6

    division = (data.get("division") or "A").strip().upper()
    roll_number = str(data.get("rollNumber") or data.get("roll_number") or "").strip() or None

    # Handle PRN generation & duplicate verification (Module 1.2 & Module 4)
    raw_prn = (data.get("prn") or data.get("studentId") or "").strip()
    if raw_prn:
        existing_stu = Student.query.filter(
            db.or_(Student.prn == raw_prn, Student.student_code == raw_prn)
        ).first()
        if existing_stu:
            raise ValidationError(f"Duplicate PRN: '{raw_prn}' is already registered to {existing_stu.user.full_name}.")
        prn = raw_prn
        code = raw_prn
    else:
        prn = generate_unique_prn()
        code = prn

    user = User(email=email, full_name=data["name"].strip(), phone=phone, role="student")
    user.set_password(initial_password)
    db.session.add(user)
    db.session.flush()

    student = Student(
        user_id=user.id,
        student_code=code,
        prn=prn,
        department_id=dept.id,
        year_label=year,
        semester=semester,
        division=division,
        roll_number=roll_number,
        status=data.get("status", "active"),
    )
    db.session.add(student)
    db.session.flush()

    # Automatically enroll student in courses for their Department & Semester
    from models import Course, Enrollment, FacultyAssignment
    cohort_courses = Course.query.filter(
        Course.department_id == dept.id,
        db.or_(
            Course.semester == semester,
            Course.faculty_assignments.any(
                db.and_(
                    FacultyAssignment.semester == semester,
                    db.or_(FacultyAssignment.division == division, FacultyAssignment.division == "ALL")
                )
            )
        )
    ).all()

    # Also handle explicitly selected course IDs if supplied
    explicit_courses = data.get("courseIds") or data.get("courses") or []
    if isinstance(explicit_courses, list):
        for cid in explicit_courses:
            c_obj = Course.query.get(cid) if str(cid).isdigit() else Course.query.filter_by(code=str(cid)).first()
            if c_obj and c_obj not in cohort_courses:
                cohort_courses.append(c_obj)

    for c in cohort_courses:
        exists = Enrollment.query.filter_by(student_id=student.id, course_id=c.id).first()
        if not exists:
            db.session.add(Enrollment(student_id=student.id, course_id=c.id))

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        raise ValidationError(f"Database constraint violation: {str(e.orig) if hasattr(e, 'orig') else 'Duplicate record'}")

    return jsonify({"success": True, "data": student.to_dict()}), 201


@bp.put("/<string:student_code>")
@roles_required("admin")
def update_student(student_code):
    student = Student.query.filter(
        db.or_(Student.student_code == student_code, Student.prn == student_code)
    ).first()
    if not student:
        return jsonify({"success": False, "error": "Student not found."}), 404

    data = request.get_json(silent=True) or {}
    if "name" in data and data["name"].strip():
        student.user.full_name = data["name"].strip()
    if "phone" in data:
        phone = validate_phone(str(data["phone"]).strip())
        if not phone:
            raise ValidationError("Phone number cannot be empty.")
        student.user.phone = phone
    if "department" in data:
        dept = Department.resolve(data["department"])
        if not dept:
            raise ValidationError(f"Unknown department: {data['department']}")
        student.department_id = dept.id
    if "year" in data and data["year"].strip():
        student.year_label = data["year"].strip()
    if "semester" in data:
        try:
            student.semester = int(data["semester"])
        except (ValueError, TypeError):
            pass
    if "division" in data and data["division"].strip():
        student.division = data["division"].strip().upper()
    if "rollNumber" in data or "roll_number" in data:
        student.roll_number = str(data.get("rollNumber") or data.get("roll_number") or "").strip()
    if "prn" in data and data["prn"].strip():
        student.prn = data["prn"].strip()
    if "status" in data:
        student.status = data["status"]

    # Re-sync enrollments for new semester/department if any
    from models import Course, Enrollment
    cohort_courses = Course.query.filter_by(department_id=student.department_id, semester=student.semester).all()
    for c in cohort_courses:
        exists = Enrollment.query.filter_by(student_id=student.id, course_id=c.id).first()
        if not exists:
            db.session.add(Enrollment(student_id=student.id, course_id=c.id))

    db.session.commit()
    return jsonify({"success": True, "data": student.to_dict()})


@bp.delete("/<string:student_code>")
@roles_required("admin")
def delete_student(student_code):
    q = Student.query.filter(
        db.or_(Student.student_code == student_code, Student.prn == student_code)
    )
    if student_code.isdigit():
        q = Student.query.filter(
            db.or_(Student.id == int(student_code), Student.student_code == student_code, Student.prn == student_code)
        )
    student = q.first()
    if not student:
        return jsonify({"success": False, "error": "Student not found."}), 404
    user = student.user
    db.session.delete(student)
    db.session.delete(user)
    db.session.commit()
    return jsonify({"success": True})
