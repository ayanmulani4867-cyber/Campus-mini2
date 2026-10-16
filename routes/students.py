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
    q = Student.query.options(
        db.joinedload(Student.user),
        db.joinedload(Student.department)
    )
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
    if not student and student_code.isdigit():
        student = Student.query.filter(
            db.or_(Student.id == int(student_code), Student.user_id == int(student_code))
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

    # Idempotent retry handling: if student already exists and hasn't logged in, resend welcome email
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        if existing_user.student_profile:
            from models import UserSession
            has_logged_in = UserSession.query.filter_by(user_id=existing_user.id).count() > 0
            if not has_logged_in:
                from services.firebase_service import firebase_service
                from services.email_service import email_service
                link = firebase_service.generate_password_reset_link(email)
                email_res = email_service.send_welcome_email(existing_user, existing_user.student_profile, link)
                return jsonify({
                    "success": True,
                    "message": f"Student account already exists for {email}. Resent welcome email with a fresh password setup link.",
                    "data": existing_user.student_profile.to_dict(),
                    "emailDelivery": {
                        "sent": email_res.get("success", False),
                        "recipient": email,
                        "messageId": email_res.get("message_id"),
                        "simulated": email_res.get("simulated", False),
                        "error": email_res.get("error"),
                    }
                }), 200
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

    import secrets
    initial_pwd = phone if phone else secrets.token_urlsafe(16)
    user = User(
        email=email,
        full_name=data["name"].strip(),
        phone=phone,
        role="student",
        must_change_password=True,
    )
    user.set_password(initial_pwd)
    db.session.add(user)
    db.session.flush()

    # Sync initial credential to Firebase Auth
    from services.firebase_service import firebase_service
    firebase_service.sync_user_to_firebase_auth(
        uid=str(user.id),
        email=user.email,
        password=initial_pwd,
        display_name=user.full_name,
        role=user.role,
    )

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

    # Generate Firebase password setup link and dispatch Brevo welcome email
    from services.firebase_service import firebase_service
    from services.email_service import email_service
    setup_link = firebase_service.generate_password_reset_link(user.email)
    email_res = email_service.send_welcome_email(user, student, setup_link)

    return jsonify({
        "success": True,
        "data": student.to_dict(),
        "emailDelivery": {
            "sent": email_res.get("success", False),
            "recipient": user.email,
            "messageId": email_res.get("message_id"),
            "simulated": email_res.get("simulated", False),
            "error": email_res.get("error"),
        }
    }), 201


@bp.post("/<string:student_code>/resend-welcome-email")
@roles_required("admin")
def resend_student_welcome_email(student_code):
    """Admin endpoint to re-trigger a Brevo welcome email with a fresh Firebase password setup link."""
    student = Student.query.filter(
        db.or_(Student.student_code == student_code, Student.prn == student_code)
    ).first()
    if not student and student_code.isdigit():
        student = Student.query.filter(
            db.or_(Student.id == int(student_code), Student.user_id == int(student_code))
        ).first()
    if not student:
        return jsonify({"success": False, "error": "Student not found."}), 404

    from services.firebase_service import firebase_service
    from services.email_service import email_service
    link = firebase_service.generate_password_reset_link(student.user.email)
    email_res = email_service.send_welcome_email(student.user, student, link)

    return jsonify({
        "success": email_res.get("success", False),
        "message": "Welcome email resent successfully." if email_res.get("success") else "Failed to send email.",
        "emailDelivery": {
            "sent": email_res.get("success", False),
            "recipient": student.user.email,
            "messageId": email_res.get("message_id"),
            "simulated": email_res.get("simulated", False),
            "error": email_res.get("error"),
        }
    }), (200 if email_res.get("success") else 500)


@bp.put("/<string:student_code>")
@roles_required("admin")
def update_student(student_code):
    student = Student.query.filter(
        db.or_(Student.student_code == student_code, Student.prn == student_code)
    ).first()
    if not student and str(student_code).isdigit():
        student = Student.query.filter(
            db.or_(Student.id == int(student_code), Student.user_id == int(student_code))
        ).first()
    if not student:
        return jsonify({"success": False, "error": "Student not found."}), 404

    data = request.get_json(silent=True) or {}

    # 1. Update Full Name
    if "name" in data and data["name"].strip():
        student.user.full_name = data["name"].strip()

    # 2. Update Email Address
    if "email" in data and data["email"].strip():
        new_email = validate_email(data["email"].strip().lower())
        if new_email != student.user.email.lower():
            dup_user = User.query.filter(User.email.ilike(new_email), User.id != student.user.id).first()
            if dup_user:
                return jsonify({"success": False, "error": f"Email '{new_email}' is already in use by another user."}), 400
            student.user.email = new_email
            from services.firebase_service import firebase_service
            if firebase_service.is_live:
                try:
                    firebase_service.sync_user_to_firebase_auth(
                        uid=str(student.user.id),
                        email=new_email,
                        display_name=student.user.full_name,
                        role="student"
                    )
                except Exception as ex:
                    logger.warning("Could not sync email update to Firebase Auth: %s", ex)

    # 3. Update Phone Number
    if "phone" in data:
        phone = validate_phone(str(data["phone"]).strip())
        if not phone:
            raise ValidationError("Phone number cannot be empty.")
        student.user.phone = phone

    # 4. Update PRN / Student Code
    new_prn = (data.get("prn") or data.get("studentCode") or data.get("student_code") or "").strip()
    if new_prn and new_prn != student.prn:
        dup_student = Student.query.filter(
            db.or_(Student.prn == new_prn, Student.student_code == new_prn),
            Student.id != student.id
        ).first()
        if dup_student:
            return jsonify({"success": False, "error": f"PRN / Student ID '{new_prn}' is already in use."}), 400
        student.prn = new_prn
        student.student_code = new_prn

    # 5. Update Roll Number
    if "rollNumber" in data or "roll_number" in data:
        student.roll_number = str(data.get("rollNumber") or data.get("roll_number") or "").strip() or None

    # 6. Update Department
    if "department" in data:
        dept = Department.resolve(data["department"])
        if not dept:
            raise ValidationError(f"Unknown department: {data['department']}")
        student.department_id = dept.id

    # 7. Update Academic Year
    if "year" in data and data["year"].strip():
        student.year_label = data["year"].strip()

    # 8. Update Semester
    if "semester" in data:
        try:
            student.semester = int(data["semester"])
        except (ValueError, TypeError):
            pass

    # 9. Update Division
    if "division" in data and data["division"].strip():
        student.division = data["division"].strip().upper()

    # 10. Update Status
    if "status" in data and data["status"].strip():
        st_val = data["status"].strip().lower()
        student.status = "active" if st_val in ("active", "true", "1") else "inactive"
        student.user.is_active = (student.status == "active")

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
            db.or_(
                Student.id == int(student_code),
                Student.user_id == int(student_code),
                Student.student_code == student_code,
                Student.prn == student_code
            )
        )
    student = q.first()
    if not student:
        return jsonify({"success": False, "error": "Student not found."}), 404
    user = student.user
    db.session.delete(student)
    db.session.delete(user)
    db.session.commit()
    return jsonify({"success": True})
