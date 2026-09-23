"""expand_course_category

Revision ID: 0002_expand_course_category
Revises: 0001_baseline
Create Date: 2026-09-23 20:30:00.000000

Expands the ck_course_category check constraint to permit core, elective, practical, laboratory, open elective, and lab.
"""
from alembic import op
import sqlalchemy as sa


revision = '0002_expand_course_category'
down_revision = '0001_baseline'
branch_labels = None
depends_on = None


def upgrade():
    # Drop existing restricted check constraint if present and re-create expanded constraint
    op.execute("ALTER TABLE courses DROP CONSTRAINT IF EXISTS ck_course_category;")
    op.create_check_constraint(
        'ck_course_category',
        'courses',
        "category IN ('core', 'elective', 'practical', 'laboratory', 'open elective', 'lab')"
    )


def downgrade():
    op.execute("ALTER TABLE courses DROP CONSTRAINT IF EXISTS ck_course_category;")
    op.create_check_constraint(
        'ck_course_category',
        'courses',
        "category IN ('core', 'lab')"
    )
