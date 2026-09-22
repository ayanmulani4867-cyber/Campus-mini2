from datetime import datetime, timezone
from extensions import db


class Department(db.Model):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)

    students = db.relationship("Student", back_populates="department")
    faculty = db.relationship("Faculty", back_populates="department")
    courses = db.relationship("Course", back_populates="department")

    def to_dict(self):
        return {"id": self.id, "name": self.name, "code": self.code}


class Course(db.Model):
    """A subject/course offering. Covers both 'core theory' and 'lab' rows
    shown on the frontend's Courses page (category field distinguishes them)."""

    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    credits = db.Column(db.Integer, nullable=False, default=3)
    category = db.Column(db.String(20), nullable=False, default="core")  # core | lab
    semester = db.Column(db.Integer, nullable=False, default=1)
    room = db.Column(db.String(50))
    syllabus_coverage = db.Column(db.Integer, nullable=False, default=0)  # 0-100 %
    status = db.Column(db.String(20), nullable=False, default="active")

    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False)
    instructor_id = db.Column(db.Integer, db.ForeignKey("faculty.id"), nullable=True)

    department = db.relationship("Department", back_populates="courses")
    instructor = db.relationship("Faculty", back_populates="courses_taught")
    faculty_assignments = db.relationship(
        "FacultyAssignment", back_populates="course", cascade="all, delete-orphan"
    )

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.CheckConstraint(category.in_(("core", "lab")), name="ck_course_category"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "title": self.title,
            "credits": self.credits,
            "category": self.category,
            "semester": self.semester,
            "room": self.room,
            "syllabusCoverage": self.syllabus_coverage,
            "status": self.status,
            "department": self.department.name if self.department else None,
            "departmentId": self.department_id,
            "instructor": self.instructor.user.full_name if self.instructor else None,
            "instructorId": self.instructor_id,
        }


class Enrollment(db.Model):
    """Links a student to a course they are taking. Backs attendance/results."""

    __tablename__ = "enrollments"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)

    student = db.relationship("Student", back_populates="enrollments")
    course = db.relationship("Course")

    __table_args__ = (
        db.UniqueConstraint("student_id", "course_id", name="uq_enrollment_student_course"),
    )
