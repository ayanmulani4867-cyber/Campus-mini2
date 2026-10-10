from math import ceil
from flask import Blueprint, request, jsonify
from extensions import db
from models import User, Student, Faculty, Department, Course, Enrollment, FacultyAssignment, Result
from utils.auth import roles_required, current_user
from utils.validators import ValidationError

bp = Blueprint("users", __name__, url_prefix="/api/users")


@bp.get("/filters")
@roles_required("admin")
def get_user_filters():
    """Module 1: Get available filters (departments, roles, semesters, divisions, statuses) and directory summary stats."""
    depts = Department.query.order_by(Department.name).all()
    dept_list = [{"id": d.id, "name": d.name, "code": d.code} for d in depts]

    total_students = Student.query.count()
    total_faculty = Faculty.query.count()
    total_admins = User.query.filter_by(role="admin").count()
    total_users_all = User.query.count()
    total_departments = len(depts)

    filter_data = {
        "departments": dept_list,
        "roles": [
            {"value": "all", "label": "All Roles"},
            {"value": "student", "label": "Students"},
            {"value": "faculty", "label": "Faculty Members"},
            {"value": "hod", "label": "Heads of Dept (HODs)"},
            {"value": "admin", "label": "Administrators"}
        ],
        "semesters": [1, 2, 3, 4, 5, 6, 7, 8],
        "divisions": ["A", "B", "C", "D"],
        "statuses": [
            {"value": "active", "label": "Active"},
            {"value": "inactive", "label": "Inactive"}
        ],
        "stats": {
            "totalUsers": total_users_all,
            "totalStudents": total_students,
            "totalFaculty": total_faculty,
            "totalAdmin": total_admins,
            "totalDepartments": total_departments,
        }
    }

    return jsonify({
        "success": True,
        "data": filter_data,
        "departments": dept_list,
        "roles": filter_data["roles"],
        "stats": filter_data["stats"],
    })


@bp.route("", methods=["GET"], strict_slashes=False)
@roles_required("admin")
def list_users():
    """Module 1: Searchable, filterable User Directory for Administrators with server-side pagination,
    dynamic department filtering, role filtering, multi-field search, and sorting."""
    # Base query joining polymorphic profile tables
    q = db.session.query(
        User,
        Student,
        Faculty,
        Department
    ).outerjoin(
        Student, User.id == Student.user_id
    ).outerjoin(
        Faculty, User.id == Faculty.user_id
    ).outerjoin(
        Department, db.or_(Student.department_id == Department.id, Faculty.department_id == Department.id)
    )

    # 1. Search filter: name, roll number, PRN/enrollment, employee ID, email, phone, designation, user ID
    search = (request.args.get("q") or request.args.get("search") or "").strip()
    if search:
        search_like = f"%{search}%"
        search_conditions = [
            User.full_name.ilike(search_like),
            User.email.ilike(search_like),
            User.phone.ilike(search_like),
            Student.student_code.ilike(search_like),
            Student.prn.ilike(search_like),
            Student.roll_number.ilike(search_like),
            Faculty.faculty_code.ilike(search_like),
            Faculty.designation.ilike(search_like),
        ]
        if search.isdigit():
            search_conditions.append(User.id == int(search))
        q = q.filter(db.or_(*search_conditions))

    # 2. Role filter: All, Students, Faculty, Administrators, HODs
    role = (request.args.get("role") or "").strip().lower()
    if role and role not in ("all", "all users"):
        if role in ("hod", "hods", "head of department"):
            q = q.filter(User.role == "faculty", Faculty.designation.ilike("%HOD%"))
        elif role in ("student", "students"):
            q = q.filter(User.role == "student")
        elif role in ("faculty", "faculties", "faculty member", "faculty members"):
            q = q.filter(User.role == "faculty")
        elif role in ("admin", "administrator", "administrators"):
            q = q.filter(User.role == "admin")

    # 3. Dynamic Department filter (handles ID, code, name, and canonical alias via Department.resolve)
    dept_ref = (request.args.get("department") or request.args.get("dept") or "").strip()
    if dept_ref and dept_ref.lower() not in ("all", "all departments", ""):
        if dept_ref.isdigit():
            q = q.filter(Department.id == int(dept_ref))
        else:
            resolved_dept = Department.resolve(dept_ref)
            if resolved_dept:
                q = q.filter(Department.id == resolved_dept.id)
            else:
                q = q.filter(db.or_(Department.code.ilike(f"%{dept_ref}%"), Department.name.ilike(f"%{dept_ref}%")))

    # 4. Semester filter
    sem_val = request.args.get("semester")
    if sem_val and str(sem_val).isdigit():
        q = q.filter(Student.semester == int(sem_val))

    # 5. Division filter
    div_val = (request.args.get("division") or "").strip().upper()
    if div_val and div_val not in ("ALL", ""):
        q = q.filter(Student.division == div_val)

    # 6. Academic year / year_label filter
    year_val = (request.args.get("year") or request.args.get("academic_year") or "").strip()
    if year_val and year_val.lower() not in ("all", ""):
        q = q.filter(Student.year_label.ilike(f"%{year_val}%"))

    # 7. Account status filter
    status_val = (request.args.get("status") or "").strip().lower()
    if status_val == "active":
        q = q.filter(User.is_active == True)  # noqa: E712
    elif status_val == "inactive":
        q = q.filter(User.is_active == False)  # noqa: E712

    # 8. Course filter (enrolled students or assigned faculty)
    course_ref = (request.args.get("course") or request.args.get("courseCode") or "").strip()
    if course_ref:
        course = Course.query.filter(
            db.or_(Course.code.ilike(course_ref), Course.id == int(course_ref) if course_ref.isdigit() else False)
        ).first()
        if course:
            enrolled_user_ids = db.session.query(Student.user_id).join(
                Enrollment, Student.id == Enrollment.student_id
            ).filter(Enrollment.course_id == course.id).subquery()

            assigned_user_ids = db.session.query(Faculty.user_id).join(
                FacultyAssignment, Faculty.id == FacultyAssignment.faculty_id
            ).filter(FacultyAssignment.course_id == course.id).subquery()

            q = q.filter(db.or_(
                User.id.in_(enrolled_user_ids),
                User.id.in_(assigned_user_ids)
            ))

    # Total filtered count
    total_count = q.count()

    # Sorting
    sort_by = (request.args.get("sort_by") or "name").lower()
    sort_order = (request.args.get("sort_order") or "asc").lower()
    if sort_by == "id":
        sort_col = User.id
    elif sort_by == "role":
        sort_col = User.role
    elif sort_by == "department":
        sort_col = Department.name
    elif sort_by == "created_at":
        sort_col = User.created_at
    else:
        sort_col = User.full_name

    if sort_order == "desc":
        q = q.order_by(sort_col.desc())
    else:
        q = q.order_by(sort_col.asc())

    # Pagination
    try:
        page = max(1, int(request.args.get("page", 1)))
        limit = min(100, max(1, int(request.args.get("limit", 20))))
    except (ValueError, TypeError):
        page = 1
        limit = 20

    records = q.offset((page - 1) * limit).limit(limit).all()

    # Format result items (never expose password_hash or secret tokens)
    items = []
    for user_obj, stu_obj, fac_obj, dept_obj in records:
        role_label = user_obj.role_label
        is_hod = False
        designation = None
        roll_num = None
        prn = None
        public_id = user_obj.public_id
        semester = None
        division = None
        year_label = None

        if user_obj.role == "student" and stu_obj:
            roll_num = stu_obj.roll_number
            prn = stu_obj.prn
            public_id = stu_obj.prn or stu_obj.student_code
            semester = stu_obj.semester
            division = stu_obj.division
            year_label = stu_obj.year_label
        elif user_obj.role == "faculty" and fac_obj:
            public_id = fac_obj.faculty_code
            designation = fac_obj.designation
            if designation and ("hod" in designation.lower() or "head" in designation.lower()):
                is_hod = True
                role_label = f"Faculty ({designation})"

        items.append({
            "id": user_obj.id,
            "name": user_obj.full_name,
            "email": user_obj.email,
            "phone": user_obj.phone,
            "role": user_obj.role,
            "roleLabel": role_label,
            "isHod": is_hod,
            "publicId": public_id,
            "rollNumber": roll_num,
            "prn": prn,
            "employeeId": fac_obj.faculty_code if fac_obj else None,
            "department": dept_obj.name if dept_obj else ("Administration" if user_obj.role == "admin" else None),
            "departmentCode": dept_obj.code if dept_obj else ("ADM" if user_obj.role == "admin" else None),
            "departmentId": dept_obj.id if dept_obj else None,
            "designation": designation,
            "semester": semester,
            "division": division,
            "year": year_label,
            "status": "Active" if user_obj.is_active else "Inactive",
            "isActive": user_obj.is_active,
            "studentId": stu_obj.student_code if stu_obj else None,
            "facultyCode": fac_obj.faculty_code if fac_obj else None,
            "createdAt": user_obj.created_at.isoformat() if user_obj.created_at else None,
        })

    # Summary directory counts
    total_students = Student.query.count()
    total_faculty = Faculty.query.count()
    total_admins = User.query.filter_by(role="admin").count()
    total_users_all = User.query.count()
    total_departments = Department.query.count()

    return jsonify({
        "success": True,
        "data": items,
        "pagination": {
            "total": total_count,
            "page": page,
            "limit": limit,
            "totalPages": ceil(total_count / limit) if limit else 1,
        },
        "stats": {
            "totalUsers": total_users_all,
            "totalStudents": total_students,
            "totalFaculty": total_faculty,
            "totalAdmin": total_admins,
            "totalDepartments": total_departments,
        }
    })


@bp.get("/<int:user_id>")
@roles_required("admin")
def get_user_detail(user_id):
    """Retrieve full member profile, enrollments, or subject assignments."""
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"success": False, "error": "User not found."}), 404

    data = user.to_dict()
    if user.student_profile:
        # Enrolled courses
        enrs = Enrollment.query.filter_by(student_id=user.student_profile.id).all()
        data["enrolledCourses"] = [e.to_dict() for e in enrs]
        # Published results summary
        results = Result.query.filter_by(student_id=user.student_profile.id, is_published=True).all()
        data["publishedResults"] = [r.to_dict() for r in results]
    elif user.faculty_profile:
        # Teaching assignments
        fas = FacultyAssignment.query.filter_by(faculty_id=user.faculty_profile.id).all()
        data["subjectAssignments"] = [fa.to_dict() for fa in fas]

    return jsonify({"success": True, "data": data})
