from flask import Blueprint, request, jsonify
from extensions import db
from models import Result, Student, Course
from utils.auth import roles_required, login_required, current_user
from utils.validators import require_fields, validate_marks, ValidationError

bp = Blueprint("results", __name__, url_prefix="/api/results")


@bp.get("")
@login_required
def list_results():
    user = current_user()
    q = Result.query

    if user.role == "student":
        q = q.filter_by(student_id=user.student_profile.id, is_published=True)
    elif user.role == "faculty":
        faculty = user.faculty_profile
        assigned_course_ids = [a.course_id for a in faculty.assignments]
        course_code = request.args.get("courseCode")
        division = request.args.get("division")
        if course_code:
            course = Course.query.filter_by(code=course_code).first()
            q = q.filter_by(course_id=course.id if course else -1)
        else:
            q = q.join(Course).filter(
                db.or_(
                    Course.instructor_id == faculty.id,
                    Course.id.in_(assigned_course_ids) if assigned_course_ids else False
                )
            )
        if division:
            q = q.join(Student).filter(Student.division == division.strip().upper())
    else:  # admin
        student_code = request.args.get("studentId")
        course_code = request.args.get("courseCode")
        division = request.args.get("division")
        if student_code:
            student = Student.query.filter(
                db.or_(Student.student_code == student_code, Student.prn == student_code)
            ).first()
            q = q.filter_by(student_id=student.id if student else -1)
        if course_code:
            course = Course.query.filter_by(code=course_code).first()
            q = q.filter_by(course_id=course.id if course else -1)
        if division:
            q = q.join(Student).filter(Student.division == division.strip().upper())

    results = q.all()
    return jsonify({"success": True, "data": [r.to_dict() for r in results]})


@bp.post("")
@roles_required("faculty", "admin")
def enter_result():
    user = current_user()
    data = request.get_json(silent=True) or {}
    stu_ref = str(data.get("studentId") or data.get("student_id") or "").strip()
    c_code = (data.get("courseCode") or data.get("course_code") or "").strip()
    if not stu_ref or not c_code:
        require_fields(data, ["studentId", "courseCode"])

    student = Student.query.filter(
        db.or_(Student.student_code == stu_ref, Student.prn == stu_ref)
    ).first()
    if not student:
        raise ValidationError("Unknown student.")
    course = Course.query.filter_by(code=c_code).first()
    if not course:
        raise ValidationError("Unknown course.")

    if user.role == "faculty":
        fac = user.faculty_profile
        is_assigned = (course.instructor_id == fac.id) or any(
            a.course_id == course.id for a in fac.assignments
        )
        if not is_assigned:
            return jsonify({"success": False, "error": "You can only enter marks for your assigned courses."}), 403

    if "marks" in data:
        # Single combined "marks out of 100" field, as entered by the faculty
        # marks-entry sheet. Split proportionally into internal(30)/end-sem(70)
        # so it still fits the two-component grading model.
        total = validate_marks(data["marks"], 0, 100, "marks")
        internal = round(total * 0.3, 2)
        end_sem = round(total * 0.7, 2)
    else:
        internal_val = data.get("internal") if "internal" in data else data.get("internal_marks")
        end_sem_val = data.get("endSem") if "endSem" in data else (data.get("external_marks") if "external_marks" in data else data.get("end_sem"))
        if internal_val is None or end_sem_val is None:
            require_fields(data, ["internal", "endSem"])
        internal = validate_marks(internal_val, 0, 30, "internal marks")
        end_sem = validate_marks(end_sem_val, 0, 70, "end-semester marks")

    result = Result.query.filter_by(student_id=student.id, course_id=course.id).first()
    if not result:
        result = Result(student_id=student.id, course_id=course.id)
        db.session.add(result)

    result.internal_marks = internal
    result.end_sem_marks = end_sem
    result.assessment_type = data.get("assessmentType", result.assessment_type or "Semester Exam")
    result.entered_by_id = user.faculty_profile.id if user.faculty_profile else result.entered_by_id

    db.session.commit()
    return jsonify({"success": True, "data": result.to_dict()}), 201


@bp.get("/my")
@roles_required("student")
def my_results():
    user = current_user()
    student = user.student_profile
    if not student:
        return jsonify({"success": True, "data": []})
    results = Result.query.filter_by(student_id=student.id, is_published=True).all()
    return jsonify({"success": True, "data": [r.to_dict() for r in results]})


@bp.put("/<int:result_id>/publish")
@roles_required("faculty", "admin")
def toggle_publish(result_id):
    result = Result.query.get(result_id)
    if not result:
        return jsonify({"success": False, "error": "Result not found."}), 404
    data = request.get_json(silent=True) or {}
    result.is_published = bool(data.get("isPublished", True))
    db.session.commit()
    return jsonify({"success": True, "data": result.to_dict()})
