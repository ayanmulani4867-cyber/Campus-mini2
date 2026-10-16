import logging
import secrets
from datetime import datetime, date
from typing import Any, Dict
from sqlalchemy import event
from services.firebase_service import firebase_service

logger = logging.getLogger(__name__)

# Mapping from SQLAlchemy Model class names to Firebase RTDB node names
MODEL_COLLECTION_MAP = {
    "User": "users",
    "Department": "departments",
    "Course": "courses",
    "Student": "students",
    "Faculty": "faculty",
    "FacultyAssignment": "faculty_assignments",
    "Enrollment": "enrollments",
    "AttendanceSession": "attendance_sessions",
    "AttendanceRecord": "attendance_records",
    "AssessmentConfig": "assessment_configs",
    "Result": "results",
    "Assignment": "assignments",
    "AssignmentSubmission": "assignment_submissions",
    "Notice": "notices",
    "StudyMaterial": "study_materials",
    "Event": "events",
    "LeaveRequest": "leave_requests",
    "AuditLog": "audit_logs",
    "UserSession": "user_sessions",
}


def _normalize_node_dict(val: Any) -> Dict[str, Any]:
    """Converts a node to a dictionary even if Firebase RTDB serialized it as a JSON list."""
    if isinstance(val, dict):
        return val
    if isinstance(val, list):
        result = {}
        for idx, item in enumerate(val):
            if item is not None and isinstance(item, dict):
                k = str(item.get("id", idx))
                result[k] = item
        return result
    return {}


def serialize_model_for_rtdb(instance: Any) -> Dict[str, Any]:
    """Converts a SQLAlchemy model instance into a clean dictionary suitable for Firebase RTDB."""
    data = {}
    table = instance.__table__
    for column in table.columns:
        val = getattr(instance, column.name, None)
        if isinstance(val, (datetime, date)):
            data[column.name] = val.isoformat()
        elif isinstance(val, bytes):
            # Omit large binary data from RTDB JSON node to avoid quota bloat
            data[column.name] = None
        else:
            data[column.name] = val
    return data


def push_instance_to_rtdb(instance: Any):
    """Pushes an added or updated model instance directly to Firebase Realtime Database."""
    cls_name = instance.__class__.__name__
    collection = MODEL_COLLECTION_MAP.get(cls_name)
    if not collection:
        return

    instance_id = getattr(instance, "id", None)
    if instance_id is None:
        return

    path = f"{collection}/{instance_id}"
    record_dict = serialize_model_for_rtdb(instance)

    try:
        firebase_service.set_data(path, record_dict)
        logger.debug("Pushed %s to Firebase RTDB at %s", cls_name, path)

        # Sync users to Firebase Auth
        if cls_name == "User":
            pwd_to_sync = getattr(instance, "_raw_password", None)
            firebase_service.sync_user_to_firebase_auth(
                uid=str(instance.id),
                email=instance.email,
                password=pwd_to_sync,
                display_name=instance.full_name,
                role=instance.role,
            )
    except Exception as e:
        logger.warning("Error pushing %s to Firebase RTDB: %s", path, e)


def delete_instance_from_rtdb(instance: Any):
    """Deletes an instance from Firebase Realtime Database."""
    cls_name = instance.__class__.__name__
    collection = MODEL_COLLECTION_MAP.get(cls_name)
    if not collection:
        return

    instance_id = getattr(instance, "id", None)
    if instance_id is None:
        return

    path = f"{collection}/{instance_id}"
    try:
        firebase_service.delete_data(path)
        logger.debug("Deleted %s from Firebase RTDB at %s", cls_name, path)
    except Exception as e:
        logger.warning("Error deleting %s from Firebase RTDB: %s", path, e)


_HOOKS_REGISTERED = False
_IS_HYDRATING = False


def register_firebase_rtdb_hooks(db):
    """Registers SQLAlchemy session event listeners to replicate all mutations
    directly to Firebase Realtime Database in real time.
    """
    global _HOOKS_REGISTERED
    if _HOOKS_REGISTERED:
        return
    _HOOKS_REGISTERED = True

    @event.listens_for(db.session, "after_flush")
    def after_flush_sync(session, flush_context):
        global _IS_HYDRATING
        if _IS_HYDRATING:
            return

        # We collect objects to sync
        for instance in list(session.new):
            push_instance_to_rtdb(instance)
        for instance in list(session.dirty):
            push_instance_to_rtdb(instance)
        for instance in list(session.deleted):
            delete_instance_from_rtdb(instance)


def hydrate_from_firebase_rtdb(app, db):
    """Fetches the state from Firebase Realtime Database and populates the database tables.
    Runs idempotently on startup.
    """
    global _IS_HYDRATING
    import models

    logger.info("Hydrating data store from Firebase Realtime Database...")
    rtdb_root = firebase_service.get_data("") or {}
    _IS_HYDRATING = True

    try:
        with app.app_context():
            # 1. Departments
            dept_data = _normalize_node_dict(rtdb_root.get("departments", {}))
            for d_id, d_dict in dept_data.items():
                if not d_dict:
                    continue
                int_id = int(d_dict.get("id") or d_id)
                if not db.session.get(models.Department, int_id) and not models.Department.query.filter_by(code=d_dict.get("code")).first():
                    d = models.Department(
                        id=int_id,
                        name=d_dict.get("name"),
                        code=d_dict.get("code"),
                    )
                    db.session.add(d)
            db.session.commit()

            # 2. Users
            users_data = _normalize_node_dict(rtdb_root.get("users", {}))
            for u_id, u_dict in users_data.items():
                if not u_dict:
                    continue
                int_id = int(u_dict.get("id") or u_id)
                if not db.session.get(models.User, int_id) and not models.User.query.filter_by(email=u_dict.get("email")).first():
                    u = models.User(
                        id=int_id,
                        email=u_dict.get("email"),
                        password_hash=u_dict.get("password_hash") or "pbkdf2:sha256:260000$default",
                        full_name=u_dict.get("full_name") or "User",
                        phone=u_dict.get("phone"),
                        role=u_dict.get("role") or "student",
                        is_active=bool(u_dict.get("is_active", True)),
                    )
                    db.session.add(u)
            db.session.commit()

            # 3. Faculty
            fac_data = _normalize_node_dict(rtdb_root.get("faculty", {}))
            for f_id, f_dict in fac_data.items():
                if not f_dict:
                    continue
                int_id = int(f_dict.get("id") or f_id)
                if not db.session.get(models.Faculty, int_id) and not models.Faculty.query.filter_by(faculty_code=f_dict.get("faculty_code")).first():
                    f = models.Faculty(
                        id=int_id,
                        user_id=int(f_dict.get("user_id")),
                        faculty_code=f_dict.get("faculty_code"),
                        department_id=int(f_dict.get("department_id")),
                        designation=f_dict.get("designation", "Assistant Professor"),
                        status=f_dict.get("status", "active"),
                    )
                    db.session.add(f)
            db.session.commit()

            # 4. Students
            stu_data = _normalize_node_dict(rtdb_root.get("students", {}))
            for s_id, s_dict in stu_data.items():
                if not s_dict:
                    continue
                int_id = int(s_dict.get("id") or s_id)
                if not db.session.get(models.Student, int_id) and not models.Student.query.filter_by(student_code=s_dict.get("student_code")).first():
                    st = models.Student(
                        id=int_id,
                        user_id=int(s_dict.get("user_id")),
                        student_code=s_dict.get("student_code"),
                        department_id=int(s_dict.get("department_id")),
                        year_label=s_dict.get("year_label", "1st Year"),
                        semester=int(s_dict.get("semester", 1)),
                        division=s_dict.get("division", "A"),
                        roll_number=s_dict.get("roll_number"),
                        prn=s_dict.get("prn"),
                        status=s_dict.get("status", "active"),
                    )
                    db.session.add(st)
            db.session.commit()

            # 5. Courses
            crs_data = _normalize_node_dict(rtdb_root.get("courses", {}))
            for c_id, c_dict in crs_data.items():
                if not c_dict:
                    continue
                int_id = int(c_dict.get("id") or c_id)
                if not db.session.get(models.Course, int_id) and not models.Course.query.filter_by(code=c_dict.get("code")).first():
                    c = models.Course(
                        id=int_id,
                        code=c_dict.get("code"),
                        title=c_dict.get("title"),
                        credits=int(c_dict.get("credits", 3)),
                        category=c_dict.get("category", "core"),
                        semester=int(c_dict.get("semester", 1)),
                        room=c_dict.get("room"),
                        syllabus_coverage=int(c_dict.get("syllabus_coverage", 0)),
                        status=c_dict.get("status", "active"),
                        department_id=int(c_dict.get("department_id")),
                        instructor_id=int(c_dict["instructor_id"]) if c_dict.get("instructor_id") else None,
                    )
                    db.session.add(c)
            db.session.commit()

            # 6. Faculty Assignments
            fa_data = _normalize_node_dict(rtdb_root.get("faculty_assignments", {}))
            for fa_id, fa_dict in fa_data.items():
                if not fa_dict:
                    continue
                int_id = int(fa_dict.get("id") or fa_id)
                if not db.session.get(models.FacultyAssignment, int_id):
                    fa = models.FacultyAssignment(
                        id=int_id,
                        faculty_id=int(fa_dict.get("faculty_id")),
                        course_id=int(fa_dict.get("course_id")),
                        department_id=int(fa_dict["department_id"]) if fa_dict.get("department_id") else None,
                        year_label=fa_dict.get("year_label", "1st Year"),
                        semester=int(fa_dict.get("semester", 1)),
                        division=fa_dict.get("division", "A"),
                    )
                    db.session.add(fa)
            db.session.commit()

            # 7. Enrollments
            enr_data = _normalize_node_dict(rtdb_root.get("enrollments", {}))
            for e_id, e_dict in enr_data.items():
                if not e_dict:
                    continue
                int_id = int(e_dict.get("id") or e_id)
                if not db.session.get(models.Enrollment, int_id):
                    en = models.Enrollment(
                        id=int_id,
                        student_id=int(e_dict.get("student_id")),
                        course_id=int(e_dict.get("course_id")),
                    )
                    db.session.add(en)
            db.session.commit()

            # 8. Attendance Sessions & Records
            sess_data = _normalize_node_dict(rtdb_root.get("attendance_sessions", {}))
            for s_id, s_dict in sess_data.items():
                if not s_dict:
                    continue
                int_id = int(s_dict.get("id") or s_id)
                if not db.session.get(models.AttendanceSession, int_id):
                    s_date = datetime.fromisoformat(s_dict["session_date"]).date() if s_dict.get("session_date") else date.today()
                    asess = models.AttendanceSession(
                        id=int_id,
                        course_id=int(s_dict.get("course_id")),
                        marked_by_id=int(s_dict.get("marked_by_id")),
                        division=s_dict.get("division", "A"),
                        session_date=s_date,
                    )
                    db.session.add(asess)
            db.session.commit()

            rec_data = _normalize_node_dict(rtdb_root.get("attendance_records", {}))
            for r_id, r_dict in rec_data.items():
                if not r_dict:
                    continue
                int_id = int(r_dict.get("id") or r_id)
                if not db.session.get(models.AttendanceRecord, int_id):
                    ar = models.AttendanceRecord(
                        id=int_id,
                        session_id=int(r_dict.get("session_id")),
                        student_id=int(r_dict.get("student_id")),
                        status=r_dict.get("status", "present"),
                    )
                    db.session.add(ar)
            db.session.commit()

            # 9. Assessment Configs
            ac_data = _normalize_node_dict(rtdb_root.get("assessment_configs", {}))
            for ac_id, ac_dict in ac_data.items():
                if not ac_dict:
                    continue
                int_id = int(ac_dict.get("id") or ac_id)
                if not db.session.get(models.AssessmentConfig, int_id):
                    ac = models.AssessmentConfig(
                        id=int_id,
                        department_id=int(ac_dict["department_id"]) if ac_dict.get("department_id") else None,
                        course_id=int(ac_dict["course_id"]) if ac_dict.get("course_id") else None,
                        ca1_max=float(ac_dict.get("ca1_max", 20.0)),
                        ca2_max=float(ac_dict.get("ca2_max", 20.0)),
                        mid_sem_max=float(ac_dict.get("mid_sem_max", 30.0)),
                        end_sem_max=float(ac_dict.get("end_sem_max", 70.0)),
                        internal_weight=float(ac_dict.get("internal_weight", 0.3)),
                        external_weight=float(ac_dict.get("external_weight", 0.7)),
                        min_passing_pct=float(ac_dict.get("min_passing_pct", 40.0)),
                    )
                    db.session.add(ac)
            db.session.commit()

            # 10. Results
            res_data = _normalize_node_dict(rtdb_root.get("results", {}))
            for res_id, res_dict in res_data.items():
                if not res_dict:
                    continue
                int_id = int(res_dict.get("id") or res_id)
                if not db.session.get(models.Result, int_id):
                    res = models.Result(
                        id=int_id,
                        student_id=int(res_dict.get("student_id")),
                        course_id=int(res_dict.get("course_id")),
                        entered_by_id=int(res_dict["entered_by_id"]) if res_dict.get("entered_by_id") else None,
                        internal_marks=float(res_dict.get("internal_marks", 0.0)),
                        end_sem_marks=float(res_dict.get("end_sem_marks", 0.0)),
                        assessment_type=res_dict.get("assessment_type", "Semester Exam"),
                        is_published=bool(res_dict.get("is_published", False)),
                        ca1_marks=float(res_dict["ca1_marks"]) if res_dict.get("ca1_marks") is not None else None,
                        ca1_max=float(res_dict.get("ca1_max", 20.0)),
                        ca1_status=res_dict.get("ca1_status", "draft"),
                        ca2_marks=float(res_dict["ca2_marks"]) if res_dict.get("ca2_marks") is not None else None,
                        ca2_max=float(res_dict.get("ca2_max", 20.0)),
                        ca2_status=res_dict.get("ca2_status", "draft"),
                        mid_sem_marks=float(res_dict["mid_sem_marks"]) if res_dict.get("mid_sem_marks") is not None else None,
                        mid_sem_max=float(res_dict.get("mid_sem_max", 30.0)),
                        mid_sem_status=res_dict.get("mid_sem_status", "draft"),
                        end_sem_max=float(res_dict.get("end_sem_max", 70.0)),
                        end_sem_status=res_dict.get("end_sem_status", "draft"),
                        status=res_dict.get("status", "draft"),
                        attendance_status=res_dict.get("attendance_status", "present"),
                        academic_year=res_dict.get("academic_year", "2025-2026"),
                        semester=int(res_dict["semester"]) if res_dict.get("semester") else None,
                        division=res_dict.get("division"),
                    )
                    db.session.add(res)
            db.session.commit()

            # 11. Assignments & Submissions
            assign_data = _normalize_node_dict(rtdb_root.get("assignments", {}))
            for a_id, a_dict in assign_data.items():
                if not a_dict:
                    continue
                int_id = int(a_dict.get("id") or a_id)
                if not db.session.get(models.Assignment, int_id):
                    due_d = datetime.fromisoformat(a_dict["due_date"]) if a_dict.get("due_date") else datetime.now()
                    a = models.Assignment(
                        id=int_id,
                        title=a_dict.get("title"),
                        description=a_dict.get("description"),
                        course_id=int(a_dict.get("course_id")),
                        faculty_id=int(a_dict.get("faculty_id")),
                        year_label=a_dict.get("year_label"),
                        semester=int(a_dict["semester"]) if a_dict.get("semester") else None,
                        division=a_dict.get("division", "All"),
                        due_date=due_d,
                        total_points=int(a_dict.get("total_points", 10)),
                    )
                    db.session.add(a)
            db.session.commit()

            sub_data = _normalize_node_dict(rtdb_root.get("assignment_submissions", {}))
            for sub_id, sub_dict in sub_data.items():
                if not sub_dict:
                    continue
                int_id = int(sub_dict.get("id") or sub_id)
                if not db.session.get(models.AssignmentSubmission, int_id):
                    sub = models.AssignmentSubmission(
                        id=int_id,
                        assignment_id=int(sub_dict.get("assignment_id")),
                        student_id=int(sub_dict.get("student_id")),
                        submission_text=sub_dict.get("submission_text"),
                        file_name=sub_dict.get("file_name"),
                        file_path=sub_dict.get("file_path"),
                        file_size_bytes=int(sub_dict.get("file_size_bytes", 0)),
                        mime_type=sub_dict.get("mime_type"),
                        status=sub_dict.get("status", "submitted"),
                        grade=float(sub_dict["grade"]) if sub_dict.get("grade") is not None else None,
                        feedback=sub_dict.get("feedback"),
                        graded_by_id=int(sub_dict["graded_by_id"]) if sub_dict.get("graded_by_id") else None,
                        is_locked=bool(sub_dict.get("is_locked", True)),
                    )
                    db.session.add(sub)
            db.session.commit()

            # 12. Notices, Materials, Events, Leaves
            for ev_id, ev_dict in _normalize_node_dict(rtdb_root.get("events", {})).items():
                if not ev_dict:
                    continue
                int_id = int(ev_dict.get("id") or ev_id)
                if not db.session.get(models.Event, int_id):
                    e_date = datetime.fromisoformat(ev_dict["event_date"]).date() if ev_dict.get("event_date") else date.today()
                    ev = models.Event(
                        id=int_id,
                        title=ev_dict.get("title"),
                        description=ev_dict.get("description"),
                        category=ev_dict.get("category", "General"),
                        event_date=e_date,
                        location=ev_dict.get("location"),
                        created_by_id=int(ev_dict.get("created_by_id", 1)),
                    )
                    db.session.add(ev)
            db.session.commit()

            for n_id, n_dict in _normalize_node_dict(rtdb_root.get("notices", {})).items():
                if not n_dict:
                    continue
                int_id = int(n_dict.get("id") or n_id)
                if not db.session.get(models.Notice, int_id):
                    n = models.Notice(
                        id=int_id,
                        title=n_dict.get("title"),
                        category=n_dict.get("category", "General"),
                        body=n_dict.get("body", ""),
                        department_id=int(n_dict["department_id"]) if n_dict.get("department_id") else None,
                        year_label=n_dict.get("year_label"),
                        semester=int(n_dict["semester"]) if n_dict.get("semester") else None,
                        division=n_dict.get("division", "All"),
                        posted_by_id=int(n_dict.get("posted_by_id", 1)),
                    )
                    db.session.add(n)
            db.session.commit()

            for m_id, m_dict in _normalize_node_dict(rtdb_root.get("study_materials", {})).items():
                if not m_dict:
                    continue
                int_id = int(m_dict.get("id") or m_id)
                if not db.session.get(models.StudyMaterial, int_id):
                    mat = models.StudyMaterial(
                        id=int_id,
                        title=m_dict.get("title"),
                        category=m_dict.get("category", "Notes"),
                        course_id=int(m_dict["course_id"]) if m_dict.get("course_id") else None,
                        department_id=int(m_dict["department_id"]) if m_dict.get("department_id") else None,
                        file_name=m_dict.get("file_name", "document.pdf"),
                        file_size_bytes=int(m_dict.get("file_size_bytes", 0)),
                        file_path=m_dict.get("file_path"),
                        mime_type=m_dict.get("mime_type"),
                        uploaded_by_id=int(m_dict.get("uploaded_by_id", 1)),
                    )
                    db.session.add(mat)
            db.session.commit()

            for lr_id, lr_dict in _normalize_node_dict(rtdb_root.get("leave_requests", {})).items():
                if not lr_dict:
                    continue
                int_id = int(lr_dict.get("id") or lr_id)
                if not db.session.get(models.LeaveRequest, int_id):
                    lr = models.LeaveRequest(
                        id=int_id,
                        student_id=int(lr_dict.get("student_id")),
                        leave_type=lr_dict.get("leave_type", "Personal"),
                        start_date=datetime.fromisoformat(lr_dict["start_date"]).date() if lr_dict.get("start_date") else date.today(),
                        end_date=datetime.fromisoformat(lr_dict["end_date"]).date() if lr_dict.get("end_date") else date.today(),
                        reason=lr_dict.get("reason", ""),
                        status=lr_dict.get("status", "pending"),
                        reviewed_by_id=int(lr_dict["reviewed_by_id"]) if lr_dict.get("reviewed_by_id") else None,
                        review_remarks=lr_dict.get("review_remarks"),
                    )
                    db.session.add(lr)
            db.session.commit()

            # 13. User Sessions
            sess_map = _normalize_node_dict(rtdb_root.get("user_sessions", {}))
            for token_id, s_dict in sess_map.items():
                if not s_dict:
                    continue
                if not db.session.get(models.UserSession, token_id):
                    us = models.UserSession(
                        id=token_id,
                        user_id=int(s_dict.get("user_id")),
                        role=s_dict.get("role", "student"),
                        is_active=bool(s_dict.get("is_active", True)),
                    )
                    db.session.add(us)
            db.session.commit()

            # 14. Prune local records that no longer exist in Firebase RTDB
            if users_data:
                # A. Prune faculty assignments not in RTDB
                fa_map = _normalize_node_dict(rtdb_root.get('faculty_assignments', {}))
                valid_fa_ids = {int(fa_dict.get('id') or k) for k, fa_dict in fa_map.items() if fa_dict and (fa_dict.get('id') or k)}
                for fa in models.FacultyAssignment.query.all():
                    if fa.id not in valid_fa_ids:
                        db.session.delete(fa)
                db.session.commit()

                # B. Prune faculty not in RTDB
                valid_fac_ids = {int(f_dict.get('id') or k) for k, f_dict in fac_data.items() if f_dict and (f_dict.get('id') or k)}
                for f in models.Faculty.query.all():
                    if f.id not in valid_fac_ids:
                        db.session.delete(f)
                db.session.commit()

                # C. Prune students not in RTDB
                valid_stu_ids = {int(s_dict.get('id') or k) for k, s_dict in stu_data.items() if s_dict and (s_dict.get('id') or k)}
                for st in models.Student.query.all():
                    if st.id not in valid_stu_ids:
                        db.session.delete(st)
                db.session.commit()

                # D. Prune users not in RTDB (preserve default admin user 1)
                valid_user_ids = {int(u_dict.get('id') or k) for k, u_dict in users_data.items() if u_dict and (u_dict.get('id') or k)}
                valid_user_ids.add(1)
                for u in models.User.query.all():
                    if u.id not in valid_user_ids:
                        db.session.delete(u)
                db.session.commit()

                # E. Clean course instructor pointers if instructor does not exist in faculty
                for crs in models.Course.query.filter(models.Course.instructor_id.isnot(None)).all():
                    if not db.session.get(models.Faculty, crs.instructor_id):
                        crs.instructor_id = None
                db.session.commit()
    finally:
        _IS_HYDRATING = False

    logger.info("Firebase Realtime Database hydration complete.")
