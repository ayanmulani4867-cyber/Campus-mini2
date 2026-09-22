from datetime import datetime, timezone
from extensions import db


def compute_grade(total: float) -> str:
    if total >= 90:
        return "A+"
    if total >= 80:
        return "A"
    if total >= 70:
        return "B+"
    if total >= 60:
        return "B"
    if total >= 50:
        return "C"
    if total >= 40:
        return "D"
    return "F"


class Result(db.Model):
    __tablename__ = "results"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    entered_by_id = db.Column(db.Integer, db.ForeignKey("faculty.id"), nullable=True)

    internal_marks = db.Column(db.Float, nullable=False, default=0)  # out of 30
    end_sem_marks = db.Column(db.Float, nullable=False, default=0)  # out of 70
    assessment_type = db.Column(db.String(30), nullable=False, default="Semester Exam")
    is_published = db.Column(db.Boolean, nullable=False, default=False)

    student = db.relationship("Student", back_populates="results")
    course = db.relationship("Course")
    entered_by = db.relationship("Faculty")

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        db.UniqueConstraint("student_id", "course_id", name="uq_result_student_course"),
        db.CheckConstraint("internal_marks >= 0 AND internal_marks <= 30", name="ck_internal_range"),
        db.CheckConstraint("end_sem_marks >= 0 AND end_sem_marks <= 70", name="ck_endsem_range"),
    )

    @property
    def total_marks(self):
        return round(self.internal_marks + self.end_sem_marks, 2)

    @property
    def grade(self):
        return compute_grade(self.total_marks)

    def to_dict(self):
        return {
            "id": self.id,
            "studentId": self.student.student_code,
            "studentName": self.student.user.full_name,
            "courseCode": self.course.code,
            "courseTitle": self.course.title,
            "assessmentType": self.assessment_type,
            "internal": self.internal_marks,
            "endSem": self.end_sem_marks,
            "total": self.total_marks,
            "grade": self.grade,
            "isPublished": self.is_published,
        }
