from datetime import datetime, timezone
from extensions import db


def compute_grade(pct: float) -> str:
    if pct >= 90:
        return "A+"
    if pct >= 80:
        return "A"
    if pct >= 70:
        return "B+"
    if pct >= 60:
        return "B"
    if pct >= 50:
        return "C"
    if pct >= 40:
        return "D"
    return "F"


class AssessmentConfig(db.Model):
    """Institutional rules for examination assessments, weightings, and passing criteria."""
    __tablename__ = "assessment_configs"

    id = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id", ondelete="CASCADE"), nullable=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id", ondelete="CASCADE"), nullable=True)

    ca1_max = db.Column(db.Float, default=20.0, nullable=False)
    ca2_max = db.Column(db.Float, default=20.0, nullable=False)
    mid_sem_max = db.Column(db.Float, default=30.0, nullable=False)
    end_sem_max = db.Column(db.Float, default=70.0, nullable=False)

    internal_weight = db.Column(db.Float, default=0.3, nullable=False)
    external_weight = db.Column(db.Float, default=0.7, nullable=False)
    min_passing_pct = db.Column(db.Float, default=40.0, nullable=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    department = db.relationship("Department")
    course = db.relationship("Course")

    def to_dict(self):
        return {
            "id": self.id,
            "departmentId": self.department_id,
            "courseId": self.course_id,
            "ca1Max": self.ca1_max,
            "ca2Max": self.ca2_max,
            "midSemMax": self.mid_sem_max,
            "endSemMax": self.end_sem_max,
            "internalWeight": self.internal_weight,
            "externalWeight": self.external_weight,
            "minPassingPct": self.min_passing_pct,
        }


class Result(db.Model):
    """Core academic examination result record supporting full assessment lifecycle:
    CA1, CA2, Mid-Semester, and End-Semester assessments.
    Lifecycle states: draft -> submitted -> under_review -> approved -> published (or reopened)."""
    __tablename__ = "results"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    entered_by_id = db.Column(db.Integer, db.ForeignKey("faculty.id"), nullable=True)

    # Legacy compatibility fields
    internal_marks = db.Column(db.Float, nullable=False, default=0.0)
    end_sem_marks = db.Column(db.Float, nullable=False, default=0.0)
    assessment_type = db.Column(db.String(50), nullable=False, default="Semester Exam")
    is_published = db.Column(db.Boolean, nullable=False, default=False)

    # Module 2 & 3: Four separate assessments
    ca1_marks = db.Column(db.Float, nullable=True)
    ca1_max = db.Column(db.Float, default=20.0, nullable=False)
    ca1_status = db.Column(db.String(20), default="draft", nullable=False)

    ca2_marks = db.Column(db.Float, nullable=True)
    ca2_max = db.Column(db.Float, default=20.0, nullable=False)
    ca2_status = db.Column(db.String(20), default="draft", nullable=False)

    mid_sem_marks = db.Column(db.Float, nullable=True)
    mid_sem_max = db.Column(db.Float, default=30.0, nullable=False)
    mid_sem_status = db.Column(db.String(20), default="draft", nullable=False)

    end_sem_max = db.Column(db.Float, default=70.0, nullable=False)
    end_sem_status = db.Column(db.String(20), default="draft", nullable=False)

    # Overall lifecycle status: draft | submitted | under_review | approved | published | reopened
    status = db.Column(db.String(20), default="draft", nullable=False)
    attendance_status = db.Column(db.String(20), default="present", nullable=False)  # present | absent | incomplete | withheld

    academic_year = db.Column(db.String(20), default="2025-2026", nullable=False)
    semester = db.Column(db.Integer, nullable=True)
    division = db.Column(db.String(10), nullable=True)

    # Audit lifecycle stamps
    submitted_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    submitted_at = db.Column(db.DateTime, nullable=True)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    approved_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    published_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    published_at = db.Column(db.DateTime, nullable=True)
    reopened_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reopened_at = db.Column(db.DateTime, nullable=True)
    reopen_reason = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    student = db.relationship("Student", back_populates="results")
    course = db.relationship("Course")
    entered_by = db.relationship("Faculty")

    __table_args__ = (
        db.UniqueConstraint("student_id", "course_id", name="uq_result_student_course"),
        db.Index("ix_results_course_id", "course_id"),
        db.Index("ix_results_student_published", "student_id", "is_published"),
        db.Index("ix_results_status", "status"),
    )

    @property
    def internal_calculated(self):
        """Calculates internal total from CA1 + CA2 + Mid-Sem (if present) or falls back to internal_marks."""
        components = []
        if self.ca1_marks is not None:
            components.append(self.ca1_marks)
        if self.ca2_marks is not None:
            components.append(self.ca2_marks)
        if self.mid_sem_marks is not None:
            components.append(self.mid_sem_marks)

        if components:
            return round(sum(components), 2)
        return round(self.internal_marks or 0.0, 2)

    @property
    def total_marks(self):
        """Aggregate marks obtained across internal and end-semester examinations."""
        end_val = self.end_sem_marks or 0.0
        return round(self.internal_calculated + end_val, 2)

    @property
    def total_max_marks(self):
        """Maximum possible marks for this course offering."""
        internal_max = (self.ca1_max or 20.0) + (self.ca2_max or 20.0) + (self.mid_sem_max or 30.0)
        end_max = self.end_sem_max or 70.0
        # If legacy scale out of 100
        if self.ca1_marks is None and self.ca2_marks is None and self.mid_sem_marks is None:
            return 100.0
        return round(internal_max + end_max, 2)

    @property
    def percentage(self):
        max_m = self.total_max_marks
        if max_m <= 0:
            return 0.0
        return round((self.total_marks / max_m) * 100.0, 2)

    @property
    def grade(self):
        if self.attendance_status in ("absent", "withheld", "incomplete"):
            return "F"
        return compute_grade(self.percentage)

    @property
    def is_passed(self):
        if self.attendance_status in ("absent", "withheld", "incomplete"):
            return False
        # Minimum passing percentage: 40%
        return self.percentage >= 40.0

    def to_dict(self):
        return {
            "id": self.id,
            "studentId": self.student.student_code if self.student else None,
            "studentName": self.student.user.full_name if (self.student and self.student.user) else None,
            "rollNumber": self.student.roll_number if self.student else None,
            "prn": self.student.prn if self.student else None,
            "department": self.student.department.name if (self.student and self.student.department) else (self.course.department.name if self.course and self.course.department else None),
            "departmentCode": self.student.department.code if (self.student and self.student.department) else (self.course.department.code if self.course and self.course.department else None),
            "semester": self.semester or (self.course.semester if self.course else None),
            "division": self.division or (self.student.division if self.student else "A"),
            "courseCode": self.course.code if self.course else None,
            "course_code": self.course.code if self.course else None,
            "courseTitle": self.course.title if self.course else None,
            "credits": self.course.credits if self.course else 3,
            "assessmentType": self.assessment_type,
            # Four Assessments
            "ca1": self.ca1_marks,
            "ca1Marks": self.ca1_marks,
            "ca1Max": self.ca1_max,
            "ca1Status": self.ca1_status,
            "ca2": self.ca2_marks,
            "ca2Marks": self.ca2_marks,
            "ca2Max": self.ca2_max,
            "ca2Status": self.ca2_status,
            "midSem": self.mid_sem_marks,
            "midSemMarks": self.mid_sem_marks,
            "midSemMax": self.mid_sem_max,
            "midSemStatus": self.mid_sem_status,
            "endSem": self.end_sem_marks,
            "endSemMarks": self.end_sem_marks,
            "endSemMax": self.end_sem_max,
            "endSemStatus": self.end_sem_status,
            # Totals
            "internal": self.internal_calculated,
            "endSem": self.end_sem_marks,
            "total": self.total_marks,
            "maxTotal": self.total_max_marks,
            "percentage": self.percentage,
            "grade": self.grade,
            "isPassed": self.is_passed,
            "attendanceStatus": self.attendance_status,
            # Lifecycle
            "status": self.status,
            "isPublished": self.is_published,
            "academicYear": self.academic_year,
            "submittedAt": self.submitted_at.isoformat() if self.submitted_at else None,
            "approvedAt": self.approved_at.isoformat() if self.approved_at else None,
            "publishedAt": self.published_at.isoformat() if self.published_at else None,
            "reopenedAt": self.reopened_at.isoformat() if self.reopened_at else None,
            "reopenReason": self.reopen_reason,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
