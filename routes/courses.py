from flask import Blueprint, request, jsonify
from extensions import db
from models import Course, Department, Faculty
from utils.auth import roles_required, login_required, current_user
from utils.validators import require_fields, ValidationError

bp = Blueprint("courses", __name__, url_prefix="/api/courses")


@bp.get("")
@login_required
def list_courses():
    user = current_user()
    q = Course.query

    if user.role == "student":
        student = user.student_profile
        enrolled_ids = [e.course_id for e in student.enrollments]
        from models import FacultyAssignment
        q = q.filter(
            db.or_(
                db.and_(Course.department_id == student.department_id, Course.semester == student.semester),
                Course.faculty_assignments.any(
                    db.and_(
                        FacultyAssignment.department_id == student.department_id,
                        FacultyAssignment.semester == student.semester,
                        db.or_(FacultyAssignment.division == student.division, FacultyAssignment.division == "ALL")
                    )
                ),
                Course.id.in_(enrolled_ids) if enrolled_ids else False
            )
        )
    elif user.role == "faculty":
        faculty = user.faculty_profile
        assigned_ids = [a.course_id for a in faculty.assignments]
        q = q.filter(
            db.or_(
                Course.instructor_id == faculty.id,
                Course.id.in_(assigned_ids) if assigned_ids else False
            )
        )
    else:  # admin
        dept_name = request.args.get("department")
        if dept_name:
            q = q.join(Department).filter(
                db.or_(Department.name.ilike(f"%{dept_name}%"), Department.code.ilike(f"%{dept_name}%"))
            )
        sem = request.args.get("semester")
        if sem:
            try:
                q = q.filter(Course.semester == int(sem))
            except (ValueError, TypeError):
                pass

    category = request.args.get("category")
    if category and category != "all":
        q = q.filter_by(category=category)
    courses = q.order_by(Course.code).all()
    return jsonify({"success": True, "data": [c.to_dict() for c in courses]})


@bp.post("")
@roles_required("admin")
def create_course():
    data = request.get_json(silent=True) or {}
    title = data.get("title") or data.get("name")
    if not data.get("code") or not title or not data.get("department"):
        require_fields(data, ["code", "title", "department"])

    code = data["code"].strip().upper()

    # Pre-check for duplicate course code
    existing = Course.query.filter_by(code=code).first()
    if existing:
        return jsonify({"success": False, "error": f"Course with code '{code}' already exists."}), 400

    dept = Department.resolve(data["department"])
    if not dept:
        raise ValidationError(f"Unknown department: {data['department']}")

    instructor = None
    if data.get("instructorCode"):
        instructor = Faculty.query.filter_by(faculty_code=data["instructorCode"]).first()
        if not instructor:
            raise ValidationError("Unknown instructor code.")

    course = Course(
        code=code,
        title=title.strip(),
        credits=data.get("credits", 3),
        category=(data.get("category") or "core").strip().lower(),
        semester=data.get("semester", 1),
        room=data.get("room"),
        department_id=dept.id,
        instructor_id=instructor.id if instructor else None,
    )
    db.session.add(course)
    db.session.commit()
    return jsonify({"success": True, "data": course.to_dict()}), 201


@bp.put("/<string:code>")
@roles_required("admin", "faculty")
def update_course(code):
    q = Course.query.filter_by(code=code)
    if code.isdigit():
        q = Course.query.filter(db.or_(Course.id == int(code), Course.code == code))
    course = q.first()
    if not course:
        return jsonify({"success": False, "error": "Course not found."}), 404

    user = current_user()
    if user.role == "faculty" and course.instructor_id != user.faculty_profile.id:
        return jsonify({"success": False, "error": "You can only update your own courses."}), 403

    data = request.get_json(silent=True) or {}
    if "title" in data and data["title"].strip():
        course.title = data["title"].strip()
    if "department" in data:
        dept = Department.resolve(data["department"])
        if not dept:
            raise ValidationError(f"Unknown department: {data['department']}")
        course.department_id = dept.id
    if "credits" in data:
        course.credits = data["credits"]
    if "category" in data:
        course.category = str(data["category"]).strip().lower()
    if "room" in data:
        course.room = data["room"]
    if "syllabusCoverage" in data:
        coverage = int(data["syllabusCoverage"])
    if not (0 <= coverage <= 100):
        raise ValidationError("syllabusCoverage must be between 0 and 100.")
        course.syllabus_coverage = coverage
    if "status" in data:
        course.status = data["status"]

    db.session.commit()
    return jsonify({"success": True, "data": course.to_dict()})


@bp.delete("/<string:code>")
@roles_required("admin")
def delete_course(code):
    q = Course.query.filter_by(code=code)
    if code.isdigit():
        q = Course.query.filter(db.or_(Course.id == int(code), Course.code == code))
    course = q.first()
    if not course:
        return jsonify({"success": False, "error": "Course not found."}), 404
    db.session.delete(course)
    db.session.commit()
    return jsonify({"success": True})


@bp.get("/<string:code>/students")
@roles_required("admin", "faculty")
def list_course_students(code):
    q = Course.query.filter_by(code=code)
    if code.isdigit():
        q = Course.query.filter(db.or_(Course.id == int(code), Course.code == code))
    course = q.first()
    if not course:
        return jsonify({"success": False, "error": "Course not found."}), 404
    from models import Student, Enrollment
    students = Student.query.join(Enrollment).filter(Enrollment.course_id == course.id).all()
    return jsonify({"success": True, "data": [s.to_dict() for s in students]})


@bp.post("/<string:code>/enroll")
@roles_required("admin", "faculty")
def enroll_student(code):
    q = Course.query.filter_by(code=code)
    if code.isdigit():
        q = Course.query.filter(db.or_(Course.id == int(code), Course.code == code))
    course = q.first()
    if not course:
        return jsonify({"success": False, "error": "Course not found."}), 404
    data = request.get_json(silent=True) or {}
    stu_ref = str(data.get("studentId") or data.get("student_id") or "").strip()
    if not stu_ref:
        require_fields(data, ["studentId"])
    from models import Student, Enrollment
    q_stu = Student.query.filter(db.or_(Student.student_code == stu_ref, Student.prn == stu_ref))
    if stu_ref.isdigit():
        q_stu = Student.query.filter(db.or_(Student.id == int(stu_ref), Student.student_code == stu_ref, Student.prn == stu_ref))
    student = q_stu.first()
    if not student:
        return jsonify({"success": False, "error": f"Unknown student: {stu_ref}"}), 404

    existing = Enrollment.query.filter_by(student_id=student.id, course_id=course.id).first()
    if existing:
        return jsonify({"success": True, "message": "Student already enrolled in this course.", "data": existing.to_dict()})

    enr = Enrollment(student_id=student.id, course_id=course.id)
    db.session.add(enr)
    db.session.commit()
    return jsonify({"success": True, "data": enr.to_dict()}), 201


@bp.delete("/<string:code>/enroll")
@roles_required("admin")
def unenroll_student(code):
    q = Course.query.filter_by(code=code)
    if code.isdigit():
        q = Course.query.filter(db.or_(Course.id == int(code), Course.code == code))
    course = q.first()
    if not course:
        return jsonify({"success": False, "error": "Course not found."}), 404
    data = request.get_json(silent=True) or {}
    stu_ref = str(data.get("studentId") or data.get("student_id") or "").strip()
    if not stu_ref:
        require_fields(data, ["studentId"])
    from models import Student, Enrollment
    stu_ref = str(data["studentId"]).strip()
    q_stu = Student.query.filter(db.or_(Student.student_code == stu_ref, Student.prn == stu_ref))
    if stu_ref.isdigit():
        q_stu = Student.query.filter(db.or_(Student.id == int(stu_ref), Student.student_code == stu_ref, Student.prn == stu_ref))
    student = q_stu.first()
    if not student:
        return jsonify({"success": False, "error": f"Unknown student: {stu_ref}"}), 404

    enr = Enrollment.query.filter_by(student_id=student.id, course_id=course.id).first()
    if enr:
        db.session.delete(enr)
        db.session.commit()
    return jsonify({"success": True, "message": "Student unenrolled."})
