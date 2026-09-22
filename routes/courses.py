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
    require_fields(data, ["code", "title", "department"])

    dept = Department.query.filter_by(name=data["department"]).first()
    if not dept:
        raise ValidationError(f"Unknown department: {data['department']}")

    instructor = None
    if data.get("instructorCode"):
        instructor = Faculty.query.filter_by(faculty_code=data["instructorCode"]).first()
        if not instructor:
            raise ValidationError("Unknown instructor code.")

    course = Course(
        code=data["code"].strip().upper(),
        title=data["title"].strip(),
        credits=data.get("credits", 3),
        category=data.get("category", "core"),
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
    course = Course.query.filter_by(code=code).first()
    if not course:
        return jsonify({"success": False, "error": "Course not found."}), 404

    user = current_user()
    if user.role == "faculty" and course.instructor_id != user.faculty_profile.id:
        return jsonify({"success": False, "error": "You can only update your own courses."}), 403

    data = request.get_json(silent=True) or {}
    if "title" in data:
        course.title = data["title"]
    if "credits" in data:
        course.credits = data["credits"]
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
    course = Course.query.filter_by(code=code).first()
    if not course:
        return jsonify({"success": False, "error": "Course not found."}), 404
    db.session.delete(course)
    db.session.commit()
    return jsonify({"success": True})
