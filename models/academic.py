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

    @classmethod
    def resolve(cls, identifier):
        """Robustly finds or provisions a department by ID, name, code, or alias.
        Auto-provisions the 4 canonical departments if missing from the database."""
        if not identifier:
            return None
        identifier = str(identifier).strip()
        if identifier.isdigit():
            d = cls.query.get(int(identifier))
            if d:
                return d

        # 1. Exact or case-insensitive match on name or code
        d = cls.query.filter(
            db.or_(cls.name.ilike(identifier), cls.code.ilike(identifier))
        ).first()
        if d:
            return d

        # 2. Canonical mapping dictionary
        CANONICAL = {
            "computer science & engineering": ("Computer Science & Engineering", "CSE"),
            "computer science and engineering": ("Computer Science & Engineering", "CSE"),
            "computer science": ("Computer Science & Engineering", "CSE"),
            "cse": ("Computer Science & Engineering", "CSE"),
            "electronics & communication": ("Electronics & Communication", "ECE"),
            "electronics and communication": ("Electronics & Communication", "ECE"),
            "ece": ("Electronics & Communication", "ECE"),
            "mechanical engineering": ("Mechanical Engineering", "MECH"),
            "mechanical": ("Mechanical Engineering", "MECH"),
            "mech": ("Mechanical Engineering", "MECH"),
            "civil engineering": ("Civil Engineering", "CE"),
            "civil": ("Civil Engineering", "CE"),
            "ce": ("Civil Engineering", "CE"),
        }

        clean_key = identifier.lower().replace("&amp;", "&").strip()
        if clean_key in CANONICAL:
            name, code = CANONICAL[clean_key]
            d = cls.query.filter(db.or_(cls.name.ilike(name), cls.code.ilike(code))).first()
            if d:
                return d
            # Auto-provision canonical department if missing
            try:
                d = cls(name=name, code=code)
                db.session.add(d)
                db.session.flush()
                return d
            except Exception:
                db.session.rollback()
                return cls.query.filter(db.or_(cls.name.ilike(name), cls.code.ilike(code))).first()

        # 3. Flexible substring match as fallback
        return cls.query.filter(
            db.or_(
                cls.name.ilike(f"%{identifier}%"),
                cls.code.ilike(f"%{identifier}%")
            )
        ).first()


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
        db.CheckConstraint(
            category.in_(("core", "elective", "practical", "laboratory", "open elective", "lab")),
            name="ck_course_category"
        ),
    )

    def get_dependent_counts(self):
        from models import Enrollment, Result, AttendanceSession, Assignment, StudyMaterial, FacultyAssignment
        return {
            "enrollments": Enrollment.query.filter_by(course_id=self.id).count(),
            "results": Result.query.filter_by(course_id=self.id).count(),
            "attendanceSessions": AttendanceSession.query.filter_by(course_id=self.id).count(),
            "assignments": Assignment.query.filter_by(course_id=self.id).count(),
            "studyMaterials": StudyMaterial.query.filter_by(course_id=self.id).count(),
            "facultyAssignments": FacultyAssignment.query.filter_by(course_id=self.id).count(),
        }

    def to_dict(self):
        sem = self.semester or 1
        year_num = (sem + 1) // 2
        suffix = "st" if year_num == 1 else "nd" if year_num == 2 else "rd" if year_num == 3 else "th"
        year_derived = f"{year_num}{suffix} Year"
        divisions = sorted(list({a.division for a in self.faculty_assignments if a.division}))
        year_label = self.faculty_assignments[0].year_label if self.faculty_assignments else year_derived

        return {
            "id": self.id,
            "code": self.code,
            "title": self.title,
            "credits": self.credits,
            "category": self.category,
            "semester": self.semester,
            "year": year_label,
            "division": divisions[0] if len(divisions) == 1 else ("All" if not divisions else ", ".join(divisions)),
            "assignedDivisions": divisions,
            "room": self.room,
            "syllabusCoverage": self.syllabus_coverage,
            "status": self.status,
            "department": self.department.name if self.department else None,
            "departmentCode": self.department.code if self.department else None,
            "departmentId": self.department_id,
            "instructor": self.instructor.user.full_name if (self.instructor and self.instructor.user) else None,
            "instructorId": self.instructor_id,
            "instructorCode": self.instructor.faculty_code if self.instructor else None,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
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

    def to_dict(self):
        return {
            "id": self.id,
            "studentId": self.student.student_code if self.student else None,
            "studentName": self.student.user.full_name if self.student and self.student.user else None,
            "courseCode": self.course.code if self.course else None,
            "courseTitle": self.course.title if self.course else None,
        }
