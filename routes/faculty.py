from flask import Blueprint, request, jsonify
from extensions import db
from models import Faculty, User, Department
from utils.auth import roles_required, login_required
from utils.validators import require_fields, validate_email, validate_phone, ValidationError

bp = Blueprint("faculty", __name__, url_prefix="/api/faculty")

DEFAULT_PASSWORD = None


def _next_faculty_code():
    from datetime import date
    year = date.today().year
    prefix = f"FAC{year}"
    facs = Faculty.query.filter(Faculty.faculty_code.like(f"{prefix}%")).all()
    max_num = 0
    for f in facs:
        try:
            num = int(f.faculty_code[len(prefix):])
            if num > max_num:
                max_num = num
        except (ValueError, TypeError):
            pass
    candidate_num = max_num + 1
    while Faculty.query.filter_by(faculty_code=f"{prefix}{candidate_num:03d}").first() is not None:
        candidate_num += 1
    return f"{prefix}{candidate_num:03d}"


@bp.get("")
@roles_required("admin", "faculty")
def list_faculty():
    """Faculty list optionally filtered by department."""
    q = Faculty.query.options(
        db.joinedload(Faculty.user),
        db.joinedload(Faculty.department),
        db.selectinload(Faculty.assignments)
    )
    dept_param = request.args.get("department_id") or request.args.get("department")
    if dept_param:
        dept = Department.resolve(dept_param)
        if dept:
            q = q.filter_by(department_id=dept.id)
        elif dept_param.isdigit():
            q = q.filter_by(department_id=int(dept_param))

    search = request.args.get("q")
    if search:
        like = f"%{search}%"
        q = q.join(User).filter(
            db.or_(User.full_name.ilike(like), Faculty.faculty_code.ilike(like))
        )
    faculty = q.all()
    return jsonify({"success": True, "data": [f.to_dict() for f in faculty]})


@bp.get("/<string:faculty_code>")
@roles_required("admin")
def get_faculty(faculty_code):
    fac = Faculty.query.filter_by(faculty_code=faculty_code).first()
    if not fac and faculty_code.isdigit():
        fac = Faculty.query.filter(
            db.or_(Faculty.id == int(faculty_code), Faculty.user_id == int(faculty_code))
        ).first()
    if not fac:
        return jsonify({"success": False, "error": "Faculty member not found."}), 404
    return jsonify({"success": True, "data": fac.to_dict()})


def _derive_year_label(semester: int) -> str:
    sem = max(1, min(8, int(semester or 1)))
    yr = (sem + 1) // 2
    suffix = "st" if yr == 1 else "nd" if yr == 2 else "rd" if yr == 3 else "th"
    return f"{yr}{suffix} Year"


def _resolve_course(course_ref):
    if not course_ref:
        return None
    from models import Course
    ref_str = str(course_ref).strip()
    if ref_str.isdigit():
        c = db.session.get(Course, int(ref_str))
        if c:
            return c

    # 1. Exact code or exact title
    course = Course.query.filter(
        db.or_(Course.code.ilike(ref_str), Course.title.ilike(ref_str))
    ).first()
    if course:
        return course

    # 2. Substring in title (e.g. "Computer Networks" in "Computer Networks & Security")
    course = Course.query.filter(Course.title.ilike(f"%{ref_str}%")).first()
    if course:
        return course

    # 3. Code prefix (e.g. "CS601 - Database...")
    prefix = ref_str.split(" - ")[0].split(" ")[0]
    course = Course.query.filter_by(code=prefix).first()
    if course:
        return course

    # Never fabricate records if lookup fails
    return None


@bp.post("")
@roles_required("admin")
def create_faculty():
    from models import Course, FacultyAssignment
    data = request.get_json(silent=True) or {}
    require_fields(data, ["name", "email", "phone", "department"])

    email = validate_email(data["email"])
    phone = validate_phone(str(data["phone"]).strip())
    if not phone:
        raise ValidationError("Phone number is required.")

    # Idempotent retry handling: if faculty member already exists and hasn't logged in, resend welcome email
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        if existing_user.faculty_profile:
            from models import UserSession
            has_logged_in = UserSession.query.filter_by(user_id=existing_user.id).count() > 0
            if not has_logged_in:
                from services.firebase_service import firebase_service
                from services.email_service import email_service
                link = firebase_service.generate_password_reset_link(email)
                email_res = email_service.send_welcome_email(existing_user, existing_user.faculty_profile, link)
                return jsonify({
                    "success": True,
                    "message": f"Faculty account already exists for {email}. Resent welcome email with a fresh password setup link.",
                    "data": existing_user.faculty_profile.to_dict(),
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

    designation = data.get("designation", "Assistant Professor").strip()
    code = (data.get("facultyId") or "").strip() or _next_faculty_code()

    import secrets
    initial_pwd = phone if phone else secrets.token_urlsafe(16)
    user = User(
        email=email,
        full_name=data["name"].strip(),
        phone=phone,
        role="faculty",
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

    fac = Faculty(
        user_id=user.id,
        faculty_code=code,
        department_id=dept.id,
        designation=designation,
        status=data.get("status", "active"),
    )
    db.session.add(fac)
    db.session.flush()

    raw_assignments = data.get("assignments") or []
    if not raw_assignments and (data.get("subject") or data.get("courseCode")):
        raw_assignments = [{
            "courseCode": data.get("courseCode") or data.get("subject"),
            "year": data.get("teachingYear") or data.get("year", "1st Year"),
            "semester": data.get("teachingSemester") or data.get("semester", 1),
            "divisions": data.get("divisions") or data.get("division", ["A"]),
        }]

    seen_create_courses = set()
    for item in raw_assignments:
        course_ref = str(item.get("courseCode") or item.get("courseId") or item.get("subject") or "").strip()
        if not course_ref:
            continue

        course = _resolve_course(course_ref)
        if not course:
            db.session.rollback()
            return jsonify({"success": False, "error": f"Referenced course '{course_ref}' was not found. Cannot invent unverified academic records."}), 400

        if course.id in seen_create_courses:
            continue
        seen_create_courses.add(course.id)

        try:
            sem_val = int(item.get("semester") or course.semester or 1)
        except (ValueError, TypeError):
            sem_val = course.semester if course.semester else 1

        year_val = item.get("year") or item.get("year_label") or _derive_year_label(sem_val)

        raw_divs = item.get("divisions") or item.get("division") or ["A"]
        if isinstance(raw_divs, str):
            divs = [d.strip().upper() for d in raw_divs.replace(",", " ").split() if d.strip()]
        else:
            divs = [str(d).strip().upper() for d in raw_divs if str(d).strip()]
        if not divs:
            divs = ["A"]

        if course:
            for div in divs:
                exists = FacultyAssignment.query.filter_by(
                    faculty_id=fac.id, course_id=course.id, semester=sem_val, division=div
                ).first()
                if not exists:
                    db.session.add(FacultyAssignment(
                        faculty_id=fac.id,
                        course_id=course.id,
                        department_id=dept.id,
                        year_label=year_val,
                        semester=sem_val,
                        division=div,
                    ))
            if not course.instructor_id:
                course.instructor_id = fac.id

            # Auto-enroll matching students in this department & semester & division
            from models import Student, Enrollment
            matching_students = Student.query.filter(
                Student.department_id == dept.id,
                Student.semester == sem_val,
                db.or_(Student.division.in_(divs), Student.division == "ALL", Student.division.is_(None))
            ).all()
            for s in matching_students:
                if not Enrollment.query.filter_by(student_id=s.id, course_id=course.id).first():
                    db.session.add(Enrollment(student_id=s.id, course_id=course.id))

    db.session.commit()

    # Generate Firebase password setup link and dispatch Brevo welcome email
    from services.firebase_service import firebase_service
    from services.email_service import email_service
    setup_link = firebase_service.generate_password_reset_link(user.email)
    email_res = email_service.send_welcome_email(user, fac, setup_link)

    return jsonify({
        "success": True,
        "data": fac.to_dict(),
        "emailDelivery": {
            "sent": email_res.get("success", False),
            "recipient": user.email,
            "messageId": email_res.get("message_id"),
            "simulated": email_res.get("simulated", False),
            "error": email_res.get("error"),
        }
    }), 201


@bp.post("/<string:faculty_code>/resend-welcome-email")
@roles_required("admin")
def resend_faculty_welcome_email(faculty_code):
    """Admin endpoint to re-trigger a Brevo welcome email with a fresh Firebase password setup link."""
    fac = Faculty.query.filter(
        db.or_(Faculty.faculty_code == faculty_code, Faculty.id == int(faculty_code) if faculty_code.isdigit() else False)
    ).first()
    if not fac:
        return jsonify({"success": False, "error": "Faculty member not found."}), 404

    from services.firebase_service import firebase_service
    from services.email_service import email_service
    link = firebase_service.generate_password_reset_link(fac.user.email)
    email_res = email_service.send_welcome_email(fac.user, fac, link)

    return jsonify({
        "success": email_res.get("success", False),
        "message": "Welcome email resent successfully." if email_res.get("success") else "Failed to send email.",
        "emailDelivery": {
            "sent": email_res.get("success", False),
            "recipient": fac.user.email,
            "messageId": email_res.get("message_id"),
            "simulated": email_res.get("simulated", False),
            "error": email_res.get("error"),
        }
    }), (200 if email_res.get("success") else 500)


@bp.put("/<string:faculty_code>")
@roles_required("admin")
def update_faculty(faculty_code):
    from models import Course, FacultyAssignment
    q = Faculty.query.filter_by(faculty_code=faculty_code)
    if str(faculty_code).isdigit():
        q = Faculty.query.filter(
            db.or_(Faculty.id == int(faculty_code), Faculty.user_id == int(faculty_code), Faculty.faculty_code == faculty_code)
        )
    fac = q.first()
    if not fac:
        return jsonify({"success": False, "error": "Faculty member not found."}), 404

    data = request.get_json(silent=True) or {}

    # 1. Update Full Name
    if "name" in data and data["name"].strip():
        fac.user.full_name = data["name"].strip()

    # 2. Update Email Address
    if "email" in data and data["email"].strip():
        new_email = validate_email(data["email"].strip().lower())
        if new_email != fac.user.email.lower():
            dup_user = User.query.filter(User.email.ilike(new_email), User.id != fac.user.id).first()
            if dup_user:
                return jsonify({"success": False, "error": f"Email '{new_email}' is already in use by another user."}), 400
            fac.user.email = new_email
            from services.firebase_service import firebase_service
            if firebase_service.is_live:
                try:
                    firebase_service.sync_user_to_firebase_auth(
                        uid=str(fac.user.id),
                        email=new_email,
                        display_name=fac.user.full_name,
                        role="faculty"
                    )
                except Exception as ex:
                    logger.warning("Could not sync email update to Firebase Auth: %s", ex)

    # 3. Update Phone Number
    if "phone" in data:
        phone = validate_phone(str(data["phone"]).strip())
        if not phone:
            raise ValidationError("Phone number cannot be empty.")
        fac.user.phone = phone

    # 3b. Update Password if provided
    new_pw = (data.get("password") or data.get("new_password") or "").strip()
    if new_pw:
        if len(new_pw) < 6:
            return jsonify({"success": False, "error": "Password must be at least 6 characters long."}), 400
        fac.user.set_password(new_pw)
        fac.user.must_change_password = False
        from services.firebase_service import firebase_service
        if firebase_service.is_live:
            try:
                firebase_service.sync_user_to_firebase_auth(
                    uid=str(fac.user.id),
                    email=fac.user.email,
                    password=new_pw,
                    display_name=fac.user.full_name,
                    role="faculty"
                )
            except Exception as ex:
                logger.warning("Could not sync faculty password update to Firebase Auth: %s", ex)

    # 4. Update Faculty ID / Code
    new_code = (data.get("faculty_code") or data.get("facultyCode") or data.get("code") or "").strip()
    if new_code and new_code != fac.faculty_code:
        dup_faculty = Faculty.query.filter(Faculty.faculty_code == new_code, Faculty.id != fac.id).first()
        if dup_faculty:
            return jsonify({"success": False, "error": f"Faculty ID / Code '{new_code}' is already assigned to another faculty member."}), 400
        fac.faculty_code = new_code

    # 5. Update Department
    if "department" in data:
        dept = Department.resolve(data["department"])
        if not dept:
            raise ValidationError(f"Unknown department: {data['department']}")
        fac.department_id = dept.id

    # 6. Update Designation
    if "designation" in data and data["designation"].strip():
        fac.designation = data["designation"].strip()

    # 7. Update Status
    if "status" in data and data["status"].strip():
        st_val = data["status"].strip().lower()
        fac.status = "active" if st_val in ("active", "true", "1") else "inactive"
        fac.user.is_active = (fac.status == "active")

    if "assignments" in data:
        # Replace assignments: delete instances explicitly so session.deleted triggers RTDB hook
        old_assigned_course_ids = {a.course_id for a in fac.assignments}
        for old_a in list(fac.assignments):
            db.session.delete(old_a)
        db.session.flush()

        seen_update_courses = set()
        for item in data["assignments"]:
            course_ref = str(item.get("courseCode") or item.get("courseId") or item.get("subject") or "").strip()
            if not course_ref:
                continue

            course = _resolve_course(course_ref)
            if not course:
                db.session.rollback()
                return jsonify({"success": False, "error": f"Referenced course '{course_ref}' was not found. Cannot invent unverified academic records."}), 400

            if course.id in seen_update_courses:
                continue
            seen_update_courses.add(course.id)

            try:
                sem_val = int(item.get("semester") or course.semester or 1)
            except (ValueError, TypeError):
                sem_val = course.semester if course.semester else 1

            year_val = item.get("year") or item.get("year_label") or _derive_year_label(sem_val)

            raw_divs = item.get("divisions") or item.get("division") or ["A"]
            if isinstance(raw_divs, str):
                divs = [d.strip().upper() for d in raw_divs.replace(",", " ").split() if d.strip()]
            else:
                divs = [str(d).strip().upper() for d in raw_divs if str(d).strip()]
            if not divs:
                divs = ["A"]

            if course:
                for div in divs:
                    db.session.add(FacultyAssignment(
                        faculty_id=fac.id,
                        course_id=course.id,
                        department_id=fac.department_id,
                        year_label=year_val,
                        semester=sem_val,
                        division=div,
                    ))

                if not course.instructor_id:
                    course.instructor_id = fac.id

                from models import Student, Enrollment
                matching_students = Student.query.filter(
                    Student.department_id == fac.department_id,
                    Student.semester == sem_val,
                    db.or_(Student.division.in_(divs), Student.division == "ALL", Student.division.is_(None))
                ).all()
                for s in matching_students:
                    if not Enrollment.query.filter_by(student_id=s.id, course_id=course.id).first():
                        db.session.add(Enrollment(student_id=s.id, course_id=course.id))

        # Clear instructor_id on courses that were removed from this faculty member
        for removed_cid in (old_assigned_course_ids - seen_update_courses):
            removed_course = db.session.get(Course, removed_cid)
            if removed_course and removed_course.instructor_id == fac.id:
                removed_course.instructor_id = None

    db.session.commit()
    return jsonify({"success": True, "data": fac.to_dict()})


@bp.delete("/<string:faculty_code>")
@roles_required("admin")
def delete_faculty(faculty_code):
    q = Faculty.query.filter_by(faculty_code=faculty_code)
    if faculty_code.isdigit():
        q = Faculty.query.filter(
            db.or_(Faculty.id == int(faculty_code), Faculty.user_id == int(faculty_code), Faculty.faculty_code == faculty_code)
        )
    fac = q.first()
    if not fac:
        return jsonify({"success": False, "error": "Faculty member not found."}), 404
    user = fac.user
    db.session.delete(fac)
    db.session.delete(user)
    db.session.commit()
    return jsonify({"success": True})
