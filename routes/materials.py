import os
from flask import Blueprint, request, jsonify, send_from_directory
from extensions import db
from models import StudyMaterial, Course
from utils.auth import roles_required, login_required, current_user
from utils.validators import ValidationError
from services.storage_service import storage_service

bp = Blueprint("materials", __name__, url_prefix="/api/materials")


@bp.get("")
@login_required
def list_materials():
    user = current_user()
    q = StudyMaterial.query

    if user.role == "student":
        student = user.student_profile
        enrolled_ids = [e.course_id for e in student.enrollments]
        q = q.filter(
            db.or_(
                db.and_(
                    db.or_(StudyMaterial.department_id.is_(None), StudyMaterial.department_id == student.department_id),
                    db.or_(StudyMaterial.semester.is_(None), StudyMaterial.semester == student.semester),
                    db.or_(StudyMaterial.division.is_(None), StudyMaterial.division.ilike("All"), StudyMaterial.division.ilike(student.division or "A")),
                ),
                StudyMaterial.course_id.in_(enrolled_ids) if enrolled_ids else False
            )
        )
    elif user.role == "faculty":
        faculty = user.faculty_profile
        assigned_ids = [a.course_id for a in faculty.assignments]
        q = q.filter(
            db.or_(
                StudyMaterial.uploaded_by_id == user.id,
                StudyMaterial.course_id.in_(assigned_ids) if assigned_ids else False
            )
        )
    else:  # admin
        dept = request.args.get("department")
        if dept:
            from models import Department
            d = Department.query.filter_by(name=dept).first()
            if d:
                q = q.filter_by(department_id=d.id)

    course_code = request.args.get("courseCode")
    if course_code:
        course = Course.query.filter_by(code=course_code).first()
        q = q.filter_by(course_id=course.id if course else -1)

    materials = q.order_by(StudyMaterial.created_at.desc()).all()
    return jsonify({"success": True, "data": [m.to_dict() for m in materials]})


@bp.post("")
@roles_required("faculty", "admin")
def upload_material():
    """Store the actual PDF/PPT/PPTX in PostgreSQL BYTEA and record metadata."""
    from models import Department, FacultyAssignment
    user = current_user()
    title = (request.form.get("title") or "").strip()
    category = (request.form.get("category") or "Notes").strip()
    course_code = (request.form.get("courseCode") or "").strip()
    uploaded = request.files.get("file")

    if not title:
        raise ValidationError("Resource title is required.")
    if not uploaded or not uploaded.filename:
        raise ValidationError("A study material file (PDF, PPT, or PPTX) is required.")

    try:
        validated = storage_service.validate_and_read(uploaded)
    except ValueError as e:
        raise ValidationError(str(e))

    course = None
    if course_code:
        code_prefix = course_code.split(" - ")[0].split(" ")[0]
        course = Course.query.filter(
            db.or_(Course.code.ilike(code_prefix), Course.title.ilike(course_code))
        ).first()
        if not course:
            raise ValidationError("Unknown course.")

        if user.role == "faculty":
            fac = user.faculty_profile
            is_assigned = (course.instructor_id == fac.id) or any(
                a.course_id == course.id for a in fac.assignments
            )
            if not is_assigned:
                return jsonify({"success": False, "error": "You can only upload materials for your assigned courses."}), 403

    # Cohort metadata
    dept_id = None
    dept_name = request.form.get("department")
    if dept_name:
        d = Department.query.filter(
            db.or_(Department.name.ilike(dept_name.strip()), Department.code.ilike(dept_name.strip()))
        ).first()
        if d:
            dept_id = d.id
    if not dept_id and course:
        dept_id = course.department_id

    fa = None
    if user.faculty_profile and course:
        div_val = request.form.get("division") or "All"
        fa = FacultyAssignment.query.filter_by(faculty_id=user.faculty_profile.id, course_id=course.id).first()
        if div_val.lower() != "all":
            div_fa = FacultyAssignment.query.filter_by(faculty_id=user.faculty_profile.id, course_id=course.id, division=div_val.upper()).first()
            if div_fa:
                fa = div_fa

    year_label = request.form.get("year") or (fa.year_label if fa else None) or (
        "3rd Year" if (course and course.semester in (5, 6)) else
        "2nd Year" if (course and course.semester in (3, 4)) else
        "4th Year" if (course and course.semester in (7, 8)) else
        "1st Year"
    )

    try:
        semester = int(request.form.get("semester") or (fa.semester if fa else (course.semester if course else 1)))
    except (ValueError, TypeError):
        semester = course.semester if course else 1

    division = (request.form.get("division") or "All").strip()
    if division.lower() != "all":
        division = division.upper()

    material = StudyMaterial(
        title=title,
        category=category,
        course_id=course.id if course else None,
        department_id=dept_id,
        year_label=year_label,
        semester=semester,
        division=division,
        file_name=validated["file_name"],
        file_size_bytes=validated["file_size_bytes"],
        file_data=validated["file_bytes"],  # Persistent PostgreSQL BYTEA storage!
        file_path=None,                      # No dependency on ephemeral local disk
        mime_type=validated["mime_type"],
        uploaded_by_id=user.id,
    )

    try:
        db.session.add(material)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify({"success": True, "data": material.to_dict()}), 201


@bp.get("/<int:material_id>/download")
@login_required
def download_material(material_id):
    """Serve study material directly from PostgreSQL BYTEA or legacy path."""
    user = current_user()
    material = StudyMaterial.query.get(material_id)
    if not material:
        return jsonify({"success": False, "error": "Material not found."}), 404

    # Access control: ensure student cannot access materials outside their scope
    if user.role == "student":
        student = user.student_profile
        from models import Enrollment
        enrolled_ids = {e.course_id for e in Enrollment.query.filter_by(student_id=student.id).all()}
        dept_match = (material.department_id is None or material.department_id == student.department_id)
        div_match = (material.division is None or material.division.lower() == "all" or material.division.upper() == (student.division or "A").upper())
        sem_match = (material.semester is None or material.semester == student.semester or
                     (material.course and any(a.semester == student.semester for a in material.course.faculty_assignments)))
        course_match = (material.course_id in enrolled_ids) if material.course_id else False

        if not ((dept_match and sem_match and div_match) or (course_match and div_match)):
            return jsonify({"success": False, "error": "You do not have permission to download this material."}), 403

    # Primary: serve directly from PostgreSQL BYTEA
    if material.file_data:
        return storage_service.create_download_response(
            material.file_data,
            material.file_name,
            material.mime_type
        )

    # Legacy fallback if an older record had a local file
    if material.file_path:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        upload_root = os.path.join(project_root, "uploads", "materials")
        if os.path.exists(os.path.join(upload_root, material.file_path)):
            return send_from_directory(
                upload_root,
                material.file_path,
                as_attachment=True,
                download_name=material.file_name,
                mimetype=material.mime_type or None,
            )

    return jsonify({"success": False, "error": "Material file not found."}), 404


@bp.delete("/<int:material_id>")
@roles_required("faculty", "admin")
def delete_material(material_id):
    material = StudyMaterial.query.get(material_id)
    if not material:
        return jsonify({"success": False, "error": "Material not found."}), 404

    if current_user().role == "faculty" and material.uploaded_by_id != current_user().id:
        return jsonify({"success": False, "error": "You can only delete your own materials."}), 403

    db.session.delete(material)
    db.session.commit()
    return jsonify({"success": True})
