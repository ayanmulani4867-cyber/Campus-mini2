from flask import Blueprint, request, jsonify
from extensions import db
from models import Course, Department, Faculty, FacultyAssignment
from utils.auth import roles_required, login_required, current_user
from utils.validators import require_fields, ValidationError

bp = Blueprint("courses", __name__, url_prefix="/api/courses")

VALID_CATEGORIES = ("core", "elective", "practical", "laboratory", "open elective", "lab")


def _resolve_course(identifier):
    """Finds a course by integer id or string course code."""
    if not identifier:
        return None
    identifier = str(identifier).strip()
    if identifier.isdigit():
        c = Course.query.get(int(identifier))
        if c:
            return c
    return Course.query.filter(Course.code.ilike(identifier)).first()


def _derive_year_label(semester: int) -> str:
    sem = max(1, min(8, int(semester or 1)))
    yr = (sem + 1) // 2
    suffix = "st" if yr == 1 else "nd" if yr == 2 else "rd" if yr == 3 else "th"
    return f"{yr}{suffix} Year"


@bp.get("")
@login_required
def list_courses():
    user = current_user()
    q = Course.query

    if user.role == "student":
        student = user.student_profile
        enrolled_ids = [e.course_id for e in student.enrollments]
        q = q.filter(
            db.or_(
                db.and_(Course.department_id == student.department_id, Course.semester == student.semester),
                Course.faculty_assignments.any(
                    db.and_(
                        FacultyAssignment.department_id == student.department_id,
                        FacultyAssignment.semester == student.semester,
                        db.or_(FacultyAssignment.division == student.division, FacultyAssignment.division.ilike("ALL"))
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
        dept_param = request.args.get("department") or request.args.get("department_id")
        if dept_param and dept_param.lower() != "all":
            resolved_dept = Department.resolve(dept_param)
            if resolved_dept:
                q = q.filter(Course.department_id == resolved_dept.id)

        sem = request.args.get("semester")
        if sem and sem.lower() != "all":
            try:
                q = q.filter(Course.semester == int(sem))
            except (ValueError, TypeError):
                pass

        status_param = request.args.get("status")
        if status_param and status_param.lower() != "all":
            q = q.filter(Course.status.ilike(status_param.strip()))

        instructor_param = request.args.get("instructor")
        if instructor_param and instructor_param.lower() != "all":
            if instructor_param.isdigit():
                q = q.filter(Course.instructor_id == int(instructor_param))
            else:
                fac = Faculty.query.filter_by(faculty_code=instructor_param.strip()).first()
                if fac:
                    q = q.filter(Course.instructor_id == fac.id)

    # Common category filter
    category = request.args.get("category")
    if category and category.lower() != "all":
        cat_clean = category.strip().lower()
        if cat_clean == "lab":
            q = q.filter(Course.category.in_(("lab", "practical", "laboratory")))
        elif cat_clean == "core":
            q = q.filter(Course.category == "core")
        else:
            q = q.filter(Course.category.ilike(cat_clean))

    # Common search query
    search_q = request.args.get("q")
    if search_q and search_q.strip():
        term = f"%{search_q.strip()}%"
        q = q.outerjoin(Department).filter(
            db.or_(
                Course.code.ilike(term),
                Course.title.ilike(term),
                Department.name.ilike(term),
                Department.code.ilike(term),
            )
        )

    # Sorting
    sort_by = request.args.get("sortBy", "code")
    if sort_by == "title":
        q = q.order_by(Course.title.asc())
    elif sort_by == "semester":
        q = q.order_by(Course.semester.asc(), Course.code.asc())
    elif sort_by == "credits":
        q = q.order_by(Course.credits.desc(), Course.code.asc())
    elif sort_by == "coverage":
        q = q.order_by(Course.syllabus_coverage.desc())
    else:
        q = q.order_by(Course.code.asc())

    courses = q.all()
    return jsonify({"success": True, "data": [c.to_dict() for c in courses]})


@bp.get("/<string:code>")
@login_required
def get_course(code):
    course = _resolve_course(code)
    if not course:
        return jsonify({"success": False, "error": f"Course '{code}' not found."}), 404

    data = course.to_dict()
    counts = course.get_dependent_counts()
    data.update({
        "enrolledStudentsCount": counts["enrollments"],
        "attendanceSessionsCount": counts["attendanceSessions"],
        "assignmentsCount": counts["assignments"],
        "resultsCount": counts["results"],
        "studyMaterialsCount": counts["studyMaterials"],
        "facultyAssignmentsCount": counts["facultyAssignments"],
        "facultyAssignments": [a.to_dict() for a in course.faculty_assignments],
    })
    return jsonify({"success": True, "data": data})


@bp.post("")
@roles_required("admin")
def create_course():
    data = request.get_json(silent=True) or {}
    title = data.get("title") or data.get("name")
    code_raw = data.get("code")
    dept_raw = data.get("department") or data.get("departmentId") or data.get("department_id")

    if not code_raw or not str(code_raw).strip():
        raise ValidationError("Course code is required.")
    if not title or not str(title).strip():
        raise ValidationError("Course title is required.")
    if not dept_raw:
        raise ValidationError("Department is required.")

    code = str(code_raw).strip().upper()
    if len(code) > 20:
        raise ValidationError("Course code must be 20 characters or fewer.")

    # Duplicate course code check
    existing = Course.query.filter(Course.code.ilike(code)).first()
    if existing:
        return jsonify({"success": False, "error": f"Course code {code} already exists."}), 400

    dept = Department.resolve(dept_raw)
    if not dept:
        raise ValidationError(f"Unknown department: {dept_raw}")

    # Credits validation
    credits_val = 3
    if "credits" in data and data["credits"] is not None:
        try:
            credits_val = int(data["credits"])
            if credits_val <= 0 or credits_val > 12:
                raise ValueError()
        except (ValueError, TypeError):
            raise ValidationError("Credits must be a positive integer between 1 and 12.")

    # Semester validation
    sem_val = 1
    if "semester" in data and data["semester"] is not None:
        try:
            sem_val = int(data["semester"])
            if sem_val < 1 or sem_val > 8:
                raise ValueError()
        except (ValueError, TypeError):
            raise ValidationError("Semester must be an integer between 1 and 8.")

    # Category validation
    category_val = (str(data.get("category") or "core")).strip().lower()
    if category_val not in VALID_CATEGORIES:
        category_val = "core"

    # Syllabus coverage validation
    coverage_val = 0
    if "syllabusCoverage" in data or "syllabus_coverage" in data:
        cov_input = data.get("syllabusCoverage") if "syllabusCoverage" in data else data.get("syllabus_coverage")
        try:
            coverage_val = int(cov_input)
            if not (0 <= coverage_val <= 100):
                raise ValueError()
        except (ValueError, TypeError):
            raise ValidationError("Syllabus coverage must be an integer between 0 and 100.")

    # Status
    status_val = (str(data.get("status") or "active")).strip().lower()
    if status_val not in ("active", "inactive"):
        status_val = "active"

    # Room
    room_val = str(data.get("room") or "").strip() or None
    if room_val and len(room_val) > 50:
        room_val = room_val[:50]

    # Year & Division
    year_label = str(data.get("year") or "").strip() or _derive_year_label(sem_val)
    division_val = str(data.get("division") or "All").strip() or "All"

    # Instructor validation
    instructor = None
    inst_ref = data.get("instructorId") or data.get("instructor_id") or data.get("instructorCode") or data.get("instructor")
    if inst_ref and str(inst_ref).strip() and str(inst_ref).strip().lower() not in ("none", "null", ""):
        inst_ref_str = str(inst_ref).strip()
        if inst_ref_str.isdigit():
            instructor = Faculty.query.get(int(inst_ref_str))
        if not instructor:
            instructor = Faculty.query.filter(
                db.or_(
                    Faculty.faculty_code.ilike(inst_ref_str),
                    Faculty.user.has(full_name=inst_ref_str)
                )
            ).first()

        if not instructor:
            raise ValidationError(f"Unknown instructor: {inst_ref_str}")

        # Check instructor belongs to the selected department
        if instructor.department_id != dept.id:
            dept_name = instructor.department.name if instructor.department else "another department"
            return jsonify({
                "success": False,
                "error": f"Selected instructor '{instructor.user.full_name}' belongs to department '{dept_name}', not department '{dept.name}'."
            }), 400

    course = Course(
        code=code,
        title=str(title).strip(),
        credits=credits_val,
        category=category_val,
        semester=sem_val,
        room=room_val,
        syllabus_coverage=coverage_val,
        status=status_val,
        department_id=dept.id,
        instructor_id=instructor.id if instructor else None,
    )
    db.session.add(course)
    db.session.flush()

    # Synchronize FacultyAssignment if instructor is assigned
    if instructor:
        target_div = division_val if division_val.upper() in ("A", "B", "C", "D") else "ALL"
        existing_fa = FacultyAssignment.query.filter_by(
            faculty_id=instructor.id,
            course_id=course.id,
            semester=sem_val,
            division=target_div,
        ).first()
        if not existing_fa:
            fa = FacultyAssignment(
                faculty_id=instructor.id,
                course_id=course.id,
                department_id=dept.id,
                year_label=year_label,
                semester=sem_val,
                division=target_div,
            )
            db.session.add(fa)

    db.session.commit()
    return jsonify({"success": True, "message": f"Course {course.code} created successfully.", "data": course.to_dict()}), 201


@bp.put("/<string:code>")
@roles_required("admin", "faculty")
def update_course(code):
    course = _resolve_course(code)
    if not course:
        return jsonify({"success": False, "error": f"Course '{code}' not found."}), 404

    user = current_user()
    if user.role == "faculty":
        if course.instructor_id != user.faculty_profile.id:
            return jsonify({"success": False, "error": "Faculty can only update syllabus progress on their assigned courses."}), 403

    data = request.get_json(silent=True) or {}

    # Admin updates course details
    if user.role == "admin":
        if "code" in data and str(data["code"]).strip():
            new_code = str(data["code"]).strip().upper()
            if new_code != course.code:
                existing = Course.query.filter(Course.code.ilike(new_code), Course.id != course.id).first()
                if existing:
                    return jsonify({"success": False, "error": f"Course code {new_code} already exists."}), 400
                course.code = new_code

        if "title" in data and str(data["title"]).strip():
            course.title = str(data["title"]).strip()

        dept = course.department
        if "department" in data or "departmentId" in data or "department_id" in data:
            dept_ref = data.get("department") or data.get("departmentId") or data.get("department_id")
            resolved_dept = Department.resolve(dept_ref)
            if not resolved_dept:
                raise ValidationError(f"Unknown department: {dept_ref}")
            dept = resolved_dept
            course.department_id = dept.id

        if "credits" in data:
            try:
                c_val = int(data["credits"])
                if c_val <= 0 or c_val > 12:
                    raise ValueError()
                course.credits = c_val
            except (ValueError, TypeError):
                raise ValidationError("Credits must be a positive integer between 1 and 12.")

        if "category" in data:
            cat_val = str(data["category"]).strip().lower()
            if cat_val in VALID_CATEGORIES:
                course.category = cat_val

        if "semester" in data:
            try:
                s_val = int(data["semester"])
                if s_val < 1 or s_val > 8:
                    raise ValueError()
                course.semester = s_val
            except (ValueError, TypeError):
                raise ValidationError("Semester must be an integer between 1 and 8.")

        if "room" in data:
            r_val = str(data["room"]).strip() if data["room"] else None
            course.room = r_val[:50] if r_val else None

        if "status" in data:
            stat_val = str(data["status"]).strip().lower()
            if stat_val in ("active", "inactive"):
                course.status = stat_val

        # Instructor assignment
        if "instructorId" in data or "instructor" in data or "instructorCode" in data:
            inst_ref = data.get("instructorId") or data.get("instructorCode") or data.get("instructor")
            if not inst_ref or str(inst_ref).strip().lower() in ("none", "null", ""):
                course.instructor_id = None
            else:
                inst_ref_str = str(inst_ref).strip()
                instructor = None
                if inst_ref_str.isdigit():
                    instructor = Faculty.query.get(int(inst_ref_str))
                if not instructor:
                    instructor = Faculty.query.filter(
                        db.or_(Faculty.faculty_code.ilike(inst_ref_str), Faculty.user.has(full_name=inst_ref_str))
                    ).first()

                if not instructor:
                    raise ValidationError(f"Unknown instructor: {inst_ref_str}")

                if instructor.department_id != course.department_id:
                    return jsonify({
                        "success": False,
                        "error": f"Selected instructor '{instructor.user.full_name}' does not belong to the selected department."
                    }), 400

                course.instructor_id = instructor.id

                # Update or synchronize FacultyAssignment
                target_div = str(data.get("division") or "ALL").strip().upper()
                year_label = str(data.get("year") or "").strip() or _derive_year_label(course.semester)
                existing_fa = FacultyAssignment.query.filter_by(
                    faculty_id=instructor.id,
                    course_id=course.id,
                    semester=course.semester,
                    division=target_div,
                ).first()
                if not existing_fa:
                    fa = FacultyAssignment(
                        faculty_id=instructor.id,
                        course_id=course.id,
                        department_id=course.department_id,
                        year_label=year_label,
                        semester=course.semester,
                        division=target_div,
                    )
                    db.session.add(fa)

    # Syllabus coverage can be updated by admin or authorized faculty
    if "syllabusCoverage" in data or "syllabus_coverage" in data:
        cov_val = data.get("syllabusCoverage") if "syllabusCoverage" in data else data.get("syllabus_coverage")
        try:
            cov_int = int(cov_val)
            if not (0 <= cov_int <= 100):
                raise ValueError()
            course.syllabus_coverage = cov_int
        except (ValueError, TypeError):
            raise ValidationError("Syllabus coverage must be between 0 and 100.")

    db.session.commit()
    return jsonify({"success": True, "message": f"Course {course.code} updated successfully.", "data": course.to_dict()})


@bp.patch("/<string:code>/status")
@roles_required("admin")
def toggle_course_status(code):
    course = _resolve_course(code)
    if not course:
        return jsonify({"success": False, "error": f"Course '{code}' not found."}), 404

    data = request.get_json(silent=True) or {}
    new_status = data.get("status")
    if new_status:
        clean_status = str(new_status).strip().lower()
        if clean_status in ("active", "inactive"):
            course.status = clean_status
        else:
            raise ValidationError("Status must be 'active' or 'inactive'.")
    else:
        # Toggle
        course.status = "inactive" if course.status == "active" else "active"

    db.session.commit()
    return jsonify({
        "success": True,
        "message": f"Course {course.code} status changed to {course.status}.",
        "data": course.to_dict()
    })


@bp.delete("/<string:code>")
@roles_required("admin")
def delete_course(code):
    course = _resolve_course(code)
    if not course:
        return jsonify({"success": False, "error": f"Course '{code}' not found."}), 404

    counts = course.get_dependent_counts()
    has_dependents = (
        counts["enrollments"] > 0
        or counts["results"] > 0
        or counts["attendanceSessions"] > 0
        or counts["assignments"] > 0
        or counts["studyMaterials"] > 0
        or counts["facultyAssignments"] > 0
    )

    if has_dependents:
        return jsonify({
            "success": False,
            "error": "This course has associated academic records and cannot be permanently deleted.",
            "message": "This course has associated academic records and cannot be permanently deleted. You can deactivate the course instead.",
            "dependentCounts": counts,
            "canDeactivate": True,
            "courseId": course.id,
            "courseCode": course.code,
        }), 400

    db.session.delete(course)
    db.session.commit()
    return jsonify({"success": True, "message": f"Course {course.code} deleted successfully."})


@bp.get("/<string:code>/students")
@roles_required("admin", "faculty")
def list_course_students(code):
    course = _resolve_course(code)
    if not course:
        return jsonify({"success": False, "error": "Course not found."}), 404
    from models import Student, Enrollment
    students = Student.query.join(Enrollment).filter(Enrollment.course_id == course.id).all()
    return jsonify({"success": True, "data": [s.to_dict() for s in students]})


@bp.post("/<string:code>/enroll")
@roles_required("admin", "faculty")
def enroll_student(code):
    course = _resolve_course(code)
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
    course = _resolve_course(code)
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

    enr = Enrollment.query.filter_by(student_id=student.id, course_id=course.id).first()
    if enr:
        db.session.delete(enr)
        db.session.commit()
    return jsonify({"success": True, "message": "Student unenrolled."})
