"""baseline_all_tables

Revision ID: 0001_baseline
Revises: 
Create Date: 2026-09-22 18:00:00.000000

Creates ALL tables for Campus Connect in the correct dependency order.
This is the single authoritative baseline migration for a fresh database.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0001_baseline'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ── 1. departments (no FK dependencies) ──────────────────────────────
    op.create_table(
        'departments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.UniqueConstraint('name', name='uq_departments_name'),
        sa.UniqueConstraint('code', name='uq_departments_code'),
    )

    # ── 2. users (no FK dependencies) ────────────────────────────────────
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('email', sa.String(length=150), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=150), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint("role IN ('admin', 'faculty', 'student')", name='ck_users_role_valid'),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_phone', 'users', ['phone'], unique=False)

    # ── 3. students (FK → users, departments) ────────────────────────────
    op.create_table(
        'students',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('student_code', sa.String(length=30), nullable=False),
        sa.Column('department_id', sa.Integer(), sa.ForeignKey('departments.id'), nullable=False),
        sa.Column('year_label', sa.String(length=20), nullable=False, server_default=sa.text("'1st Year'")),
        sa.Column('semester', sa.Integer(), nullable=False, server_default=sa.text('1')),
        sa.Column('division', sa.String(length=10), nullable=False, server_default=sa.text("'A'")),
        sa.Column('roll_number', sa.String(length=30), nullable=True),
        sa.Column('prn', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default=sa.text("'active'")),
        sa.UniqueConstraint('user_id', name='uq_students_user_id'),
        sa.UniqueConstraint('student_code', name='uq_students_student_code'),
    )

    # ── 4. faculty (FK → users, departments) ─────────────────────────────
    op.create_table(
        'faculty',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('faculty_code', sa.String(length=30), nullable=False),
        sa.Column('department_id', sa.Integer(), sa.ForeignKey('departments.id'), nullable=False),
        sa.Column('designation', sa.String(length=80), nullable=False, server_default=sa.text("'Assistant Professor'")),
        sa.Column('status', sa.String(length=20), nullable=False, server_default=sa.text("'active'")),
        sa.UniqueConstraint('user_id', name='uq_faculty_user_id'),
        sa.UniqueConstraint('faculty_code', name='uq_faculty_faculty_code'),
    )

    # ── 5. courses (FK → departments, faculty) ───────────────────────────
    op.create_table(
        'courses',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('credits', sa.Integer(), nullable=False, server_default=sa.text('3')),
        sa.Column('category', sa.String(length=20), nullable=False, server_default=sa.text("'core'")),
        sa.Column('semester', sa.Integer(), nullable=False, server_default=sa.text('1')),
        sa.Column('room', sa.String(length=50), nullable=True),
        sa.Column('syllabus_coverage', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('status', sa.String(length=20), nullable=False, server_default=sa.text("'active'")),
        sa.Column('department_id', sa.Integer(), sa.ForeignKey('departments.id'), nullable=False),
        sa.Column('instructor_id', sa.Integer(), sa.ForeignKey('faculty.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('code', name='uq_courses_code'),
        sa.CheckConstraint("category IN ('core', 'lab')", name='ck_course_category'),
    )

    # ── 6. enrollments (FK → students, courses) ──────────────────────────
    op.create_table(
        'enrollments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id'), nullable=False),
        sa.Column('course_id', sa.Integer(), sa.ForeignKey('courses.id'), nullable=False),
        sa.UniqueConstraint('student_id', 'course_id', name='uq_enrollment_student_course'),
    )

    # ── 7. faculty_assignments (FK → faculty, courses, departments) ──────
    op.create_table(
        'faculty_assignments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('faculty_id', sa.Integer(), sa.ForeignKey('faculty.id', ondelete='CASCADE'), nullable=False),
        sa.Column('course_id', sa.Integer(), sa.ForeignKey('courses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('department_id', sa.Integer(), sa.ForeignKey('departments.id'), nullable=True),
        sa.Column('year_label', sa.String(length=20), nullable=False, server_default=sa.text("'1st Year'")),
        sa.Column('semester', sa.Integer(), nullable=False, server_default=sa.text('1')),
        sa.Column('division', sa.String(length=10), nullable=False, server_default=sa.text("'A'")),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('faculty_id', 'course_id', 'semester', 'division', name='uq_faculty_course_sem_div'),
    )
    op.create_index('ix_faculty_assignments_faculty_id', 'faculty_assignments', ['faculty_id'], unique=False)
    op.create_index('ix_faculty_assignments_course_id', 'faculty_assignments', ['course_id'], unique=False)

    # ── 8. attendance_sessions (FK → courses, faculty) ───────────────────
    op.create_table(
        'attendance_sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('course_id', sa.Integer(), sa.ForeignKey('courses.id'), nullable=False),
        sa.Column('marked_by_id', sa.Integer(), sa.ForeignKey('faculty.id'), nullable=False),
        sa.Column('division', sa.String(length=10), nullable=False, server_default=sa.text("'A'")),
        sa.Column('session_date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('course_id', 'session_date', 'division', name='uq_session_course_date_div'),
    )

    # ── 9. attendance_records (FK → attendance_sessions, students) ───────
    op.create_table(
        'attendance_records',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('attendance_sessions.id'), nullable=False),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id'), nullable=False),
        sa.Column('status', sa.String(length=10), nullable=False, server_default=sa.text("'present'")),
        sa.CheckConstraint("status IN ('present', 'absent', 'late')", name='ck_attendance_status'),
        sa.UniqueConstraint('session_id', 'student_id', name='uq_record_session_student'),
    )

    # ── 10. results (FK → students, courses, faculty) ────────────────────
    op.create_table(
        'results',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id'), nullable=False),
        sa.Column('course_id', sa.Integer(), sa.ForeignKey('courses.id'), nullable=False),
        sa.Column('entered_by_id', sa.Integer(), sa.ForeignKey('faculty.id'), nullable=True),
        sa.Column('internal_marks', sa.Float(), nullable=False, server_default=sa.text('0')),
        sa.Column('end_sem_marks', sa.Float(), nullable=False, server_default=sa.text('0')),
        sa.Column('assessment_type', sa.String(length=30), nullable=False, server_default=sa.text("'Semester Exam'")),
        sa.Column('is_published', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('student_id', 'course_id', name='uq_result_student_course'),
        sa.CheckConstraint('internal_marks >= 0 AND internal_marks <= 30', name='ck_internal_range'),
        sa.CheckConstraint('end_sem_marks >= 0 AND end_sem_marks <= 70', name='ck_endsem_range'),
    )

    # ── 11. notices (FK → users, departments) ────────────────────────────
    op.create_table(
        'notices',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('category', sa.String(length=40), nullable=False, server_default=sa.text("'General'")),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('department_id', sa.Integer(), sa.ForeignKey('departments.id'), nullable=True),
        sa.Column('year_label', sa.String(length=20), nullable=True),
        sa.Column('semester', sa.Integer(), nullable=True),
        sa.Column('division', sa.String(length=10), nullable=True, server_default=sa.text("'All'")),
        sa.Column('posted_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # ── 12. study_materials (FK → courses, departments, users) ───────────
    op.create_table(
        'study_materials',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('category', sa.String(length=40), nullable=False, server_default=sa.text("'Notes'")),
        sa.Column('course_id', sa.Integer(), sa.ForeignKey('courses.id'), nullable=True),
        sa.Column('department_id', sa.Integer(), sa.ForeignKey('departments.id'), nullable=True),
        sa.Column('year_label', sa.String(length=20), nullable=True),
        sa.Column('semester', sa.Integer(), nullable=True),
        sa.Column('division', sa.String(length=10), nullable=True, server_default=sa.text("'All'")),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('file_path', sa.String(length=500), nullable=True),
        sa.Column('file_data', sa.LargeBinary(), nullable=True),
        sa.Column('mime_type', sa.String(length=150), nullable=True),
        sa.Column('uploaded_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # ── 13. events (FK → users) ──────────────────────────────────────────
    op.create_table(
        'events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=40), nullable=False, server_default=sa.text("'General'")),
        sa.Column('event_date', sa.Date(), nullable=False),
        sa.Column('location', sa.String(length=150), nullable=True),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # ── 14. user_sessions (FK → users) ───────────────────────────────────
    op.create_table(
        'user_sessions',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_activity', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
    )
    op.create_index('ix_user_sessions_user_id', 'user_sessions', ['user_id'], unique=False)
    op.create_index('ix_user_sessions_is_active', 'user_sessions', ['is_active'], unique=False)

    # ── 15. leave_requests (FK → students, users) ─────────────────────────
    op.create_table(
        'leave_requests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id'), nullable=False),
        sa.Column('leave_type', sa.String(length=50), nullable=False, server_default=sa.text("'Personal'")),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column('reviewed_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('review_remarks', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected')", name='ck_leave_status'),
    )
    op.create_index('ix_leave_requests_student_id', 'leave_requests', ['student_id'], unique=False)
    op.create_index('ix_leave_requests_status', 'leave_requests', ['status'], unique=False)

    # ── 16. assignments (FK → courses, faculty) ───────────────────────────
    op.create_table(
        'assignments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('course_id', sa.Integer(), sa.ForeignKey('courses.id'), nullable=False),
        sa.Column('faculty_id', sa.Integer(), sa.ForeignKey('faculty.id'), nullable=False),
        sa.Column('year_label', sa.String(length=20), nullable=True),
        sa.Column('semester', sa.Integer(), nullable=True),
        sa.Column('division', sa.String(length=10), nullable=True, server_default=sa.text("'All'")),
        sa.Column('due_date', sa.DateTime(), nullable=False),
        sa.Column('total_points', sa.Integer(), nullable=False, server_default=sa.text('100')),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_assignments_course_id', 'assignments', ['course_id'], unique=False)
    op.create_index('ix_assignments_faculty_id', 'assignments', ['faculty_id'], unique=False)

    # ── 17. assignment_submissions (FK → assignments, students, faculty) ─
    op.create_table(
        'assignment_submissions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('assignment_id', sa.Integer(), sa.ForeignKey('assignments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id', ondelete='CASCADE'), nullable=False),
        sa.Column('submission_text', sa.Text(), nullable=True),
        sa.Column('file_path', sa.String(length=500), nullable=True),
        sa.Column('file_name', sa.String(length=255), nullable=True),
        sa.Column('file_data', sa.LargeBinary(), nullable=True),
        sa.Column('file_size_bytes', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('mime_type', sa.String(length=150), nullable=True),
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default=sa.text("'submitted'")),
        sa.Column('grade', sa.Float(), nullable=True),
        sa.Column('feedback', sa.Text(), nullable=True),
        sa.Column('graded_by_id', sa.Integer(), sa.ForeignKey('faculty.id'), nullable=True),
        sa.UniqueConstraint('assignment_id', 'student_id', name='uq_assignment_student'),
        sa.CheckConstraint("status IN ('submitted', 'graded', 'late')", name='ck_submission_status'),
    )
    op.create_index('ix_assignment_submissions_assignment_id', 'assignment_submissions', ['assignment_id'], unique=False)
    op.create_index('ix_assignment_submissions_student_id', 'assignment_submissions', ['student_id'], unique=False)


def downgrade():
    op.drop_table('assignment_submissions')
    op.drop_table('assignments')
    op.drop_table('leave_requests')
    op.drop_table('user_sessions')
    op.drop_table('events')
    op.drop_table('study_materials')
    op.drop_table('notices')
    op.drop_table('results')
    op.drop_table('attendance_records')
    op.drop_table('attendance_sessions')
    op.drop_table('faculty_assignments')
    op.drop_table('enrollments')
    op.drop_table('courses')
    op.drop_table('faculty')
    op.drop_table('students')
    op.drop_table('users')
    op.drop_table('departments')
