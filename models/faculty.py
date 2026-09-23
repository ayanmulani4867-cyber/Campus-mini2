from datetime import datetime, timezone
from extensions import db


class FacultyAssignment(db.Model):
    """Relational teaching assignment linking Faculty -> Course (Subject) -> Year -> Semester -> Division."""
    __tablename__ = "faculty_assignments"

    id = db.Column(db.Integer, primary_key=True)
    faculty_id = db.Column(db.Integer, db.ForeignKey("faculty.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=True)
    year_label = db.Column(db.String(20), nullable=False, default="1st Year")
    semester = db.Column(db.Integer, nullable=False, default=1)
    division = db.Column(db.String(10), nullable=False, default="A")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    faculty = db.relationship("Faculty", back_populates="assignments")
    course = db.relationship("Course", back_populates="faculty_assignments")
    department = db.relationship("Department")

    __table_args__ = (
        db.UniqueConstraint("faculty_id", "course_id", "semester", "division", name="uq_faculty_course_sem_div"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "facultyId": self.faculty_id,
            "courseId": self.course_id,
            "courseCode": self.course.code if self.course else None,
            "courseTitle": self.course.title if self.course else None,
            "department": self.department.name if self.department else (self.course.department.name if self.course and self.course.department else None),
            "departmentId": self.department_id or (self.course.department_id if self.course else None),
            "year": self.year_label,
            "semester": self.semester,
            "division": self.division,
        }


class Faculty(db.Model):
    __tablename__ = "faculty"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    faculty_code = db.Column(db.String(30), unique=True, nullable=False)  # FAC2018042
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False)
    designation = db.Column(db.String(80), nullable=False, default="Assistant Professor")
    status = db.Column(db.String(20), nullable=False, default="active")

    user = db.relationship("User", back_populates="faculty_profile")
    department = db.relationship("Department", back_populates="faculty")
    courses_taught = db.relationship("Course", back_populates="instructor")
    assignments = db.relationship(
        "FacultyAssignment", back_populates="faculty", cascade="all, delete-orphan", lazy="joined"
    )

    def _get_assignment_summaries(self):
        subjects = []
        years = []
        semesters = []
        divisions = []
        for a in self.assignments:
            title = a.course.title if a.course else None
            if title and title not in subjects:
                subjects.append(title)
            if a.year_label and a.year_label not in years:
                years.append(a.year_label)
            if a.semester and a.semester not in semesters:
                semesters.append(a.semester)
            if a.division and a.division not in divisions:
                divisions.append(a.division)

        # Fallback to courses_taught if no relational assignments yet
        if not subjects and self.courses_taught:
            for c in self.courses_taught:
                if c.title not in subjects:
                    subjects.append(c.title)
                if c.semester and c.semester not in semesters:
                    semesters.append(c.semester)

        return {
            "assignedSubjects": subjects,
            "assignedYears": sorted(years),
            "assignedSemesters": sorted(semesters),
            "assignedDivisions": sorted(divisions),
        }

    def to_profile_dict(self):
        summaries = self._get_assignment_summaries()
        return {
            "dept": self.department.name if self.department else None,
            "departmentId": self.department_id,
            "designation": self.designation,
            "assignedSubjects": summaries["assignedSubjects"],
            "assignedYears": summaries["assignedYears"],
            "assignedSemesters": summaries["assignedSemesters"],
            "assignedDivisions": summaries["assignedDivisions"],
            "assignments": [a.to_dict() for a in self.assignments],
        }

    def to_dict(self):
        summaries = self._get_assignment_summaries()
        return {
            "id": self.faculty_code,
            "facultyId": self.id,
            "facultyCode": self.faculty_code,
            "name": self.user.full_name,
            "email": self.user.email,
            "phone": self.user.phone,
            "dept": self.department.name if self.department else None,
            "departmentId": self.department_id,
            "designation": self.designation,
            "status": self.status,
            "assignedSubjects": summaries["assignedSubjects"],
            "assignedYears": summaries["assignedYears"],
            "assignedSemesters": summaries["assignedSemesters"],
            "assignedDivisions": summaries["assignedDivisions"],
            "assignments": [a.to_dict() for a in self.assignments],
        }
