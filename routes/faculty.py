from flask import Blueprint, request, jsonify
from extensions import db
from models import Faculty, User, Department
from utils.auth import roles_required, login_required
from utils.validators import require_fields, validate_email, validate_phone, ValidationError

bp = Blueprint("faculty", __name__, url_prefix="/api/faculty")

DEFAULT_PASSWORD = None


def _next_faculty_code():
    count = Faculty.query.count() + 1
    from datetime import date
    return f"FAC{date.today().year}{count:03d}"


@bp.get("")
@roles_required("admin")
def list_faculty():
    """User Directory faculty list is restricted to Administrators."""
    q = Faculty.query
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
    if not fac:
        return jsonify({"success": False, "error": "Faculty member not found."}), 404
    return jsonify({"success": True, "data": fac.to_dict()})


def _resolve_or_create_course(course_ref, dept_id, sem_val, fac_id=None):
    if not course_ref:
        return None
    from models import Course
    # 1. Exact code or exact title
    course = Course.query.filter(
        db.or_(Course.code.ilike(course_ref), Course.title.ilike(course_ref))
    ).first()
    if course:
        return course

    # 2. Substring in title (e.g. "Computer Networks" in "Computer Networks & Security")
    course = Course.query.filter(Course.title.ilike(f"%{course_ref}%")).first()
    if course:
        return course

    # 3. Code prefix (e.g. "CS601 - Database...")
    prefix = course_ref.split(" - ")[0].split(" ")[0]
    course = Course.query.filter_by(code=prefix).first()
    if course:
        return course

    # 4. If not found, create a new course record
    dept = Department.query.get(dept_id)
    dept_code = dept.code[:2] if dept and dept.code else "CS"
    count = Course.query.count() + 1
    generated_code = f"{dept_code}{sem_val}{count:02d}"
    course = Course(
        code=generated_code,
        title=course_ref,
        credits=4,
        category="core",
        semester=sem_val,
        department_id=dept_id,
        instructor_id=fac_id,
        syllabus_coverage=80
    )
    db.session.add(course)
    db.session.flush()
    return course


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
    if User.query.filter_by(email=email).first():
        raise ValidationError("A user with that email already exists.")

    dept = Department.query.filter(
        db.or_(Department.name.ilike(data["department"].strip()), Department.code.ilike(data["department"].strip()))
    ).first()
    if not dept:
        raise ValidationError(f"Unknown department: {data['department']}")

    designation = data.get("designation", "Assistant Professor").strip()
    code = (data.get("facultyId") or "").strip() or _next_faculty_code()

    user = User(email=email, full_name=data["name"].strip(), phone=phone, role="faculty")
    user.set_password(phone)  # Phone number becomes initial password
    db.session.add(user)
    db.session.flush()

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

    for item in raw_assignments:
        course_ref = str(item.get("courseCode") or item.get("courseId") or item.get("subject") or "").strip()
        if not course_ref:
            continue

        year_val = item.get("year") or item.get("year_label") or "1st Year"
        try:
            sem_val = int(item.get("semester") or 1)
        except (ValueError, TypeError):
            sem_val = 1

        course = _resolve_or_create_course(course_ref, dept.id, sem_val, fac.id)

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
    return jsonify({"success": True, "data": fac.to_dict()}), 201


@bp.put("/<string:faculty_code>")
@roles_required("admin")
def update_faculty(faculty_code):
    from models import Course, FacultyAssignment
    fac = Faculty.query.filter_by(faculty_code=faculty_code).first()
    if not fac:
        return jsonify({"success": False, "error": "Faculty member not found."}), 404

    data = request.get_json(silent=True) or {}
    if "name" in data and data["name"].strip():
        fac.user.full_name = data["name"].strip()
    if "phone" in data:
        phone = validate_phone(str(data["phone"]).strip())
        if not phone:
            raise ValidationError("Phone number cannot be empty.")
        fac.user.phone = phone
    if "department" in data:
        dept = Department.query.filter(
            db.or_(Department.name.ilike(data["department"].strip()), Department.code.ilike(data["department"].strip()))
        ).first()
        if not dept:
            raise ValidationError(f"Unknown department: {data['department']}")
        fac.department_id = dept.id
    if "designation" in data:
        fac.designation = data["designation"]
    if "status" in data:
        fac.status = data["status"]

    if "assignments" in data:
        # Replace assignments
        FacultyAssignment.query.filter_by(faculty_id=fac.id).delete()
        for item in data["assignments"]:
            course_ref = str(item.get("courseCode") or item.get("courseId") or item.get("subject") or "").strip()
            if not course_ref:
                continue
            year_val = item.get("year") or item.get("year_label") or "1st Year"
            try:
                sem_val = int(item.get("semester") or 1)
            except (ValueError, TypeError):
                sem_val = 1

            course = _resolve_or_create_course(course_ref, fac.department_id, sem_val, fac.id)

            raw_divs = item.get("divisions") or item.get("division") or ["A"]
            if isinstance(raw_divs, str):
                divs = [d.strip().upper() for d in raw_divs.replace(",", " ").split() if d.strip()]
            else:
                divs = [str(d).strip().upper() for d in raw_divs if str(d).strip()]

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

                from models import Student, Enrollment
                matching_students = Student.query.filter(
                    Student.department_id == fac.department_id,
                    Student.semester == sem_val,
                    db.or_(Student.division.in_(divs), Student.division == "ALL", Student.division.is_(None))
                ).all()
                for s in matching_students:
                    if not Enrollment.query.filter_by(student_id=s.id, course_id=course.id).first():
                        db.session.add(Enrollment(student_id=s.id, course_id=course.id))

    db.session.commit()
    return jsonify({"success": True, "data": fac.to_dict()})


@bp.delete("/<string:faculty_code>")
@roles_required("admin")
def delete_faculty(faculty_code):
    fac = Faculty.query.filter_by(faculty_code=faculty_code).first()
    if not fac:
        return jsonify({"success": False, "error": "Faculty member not found."}), 404
    user = fac.user
    db.session.delete(fac)
    db.session.delete(user)
    db.session.commit()
    return jsonify({"success": True})
