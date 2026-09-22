from datetime import datetime, timezone, date
from extensions import db


class AttendanceSession(db.Model):
    """One roll-call event for a course on a given date, marked by a faculty member."""

    __tablename__ = "attendance_sessions"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    marked_by_id = db.Column(db.Integer, db.ForeignKey("faculty.id"), nullable=False)
    division = db.Column(db.String(10), nullable=False, default="A")
    session_date = db.Column(db.Date, nullable=False, default=lambda: date.today())
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    course = db.relationship("Course")
    marked_by = db.relationship("Faculty")
    records = db.relationship(
        "AttendanceRecord", back_populates="session", cascade="all, delete-orphan"
    )

    __table_args__ = (
        db.UniqueConstraint("course_id", "session_date", "division", name="uq_session_course_date_div"),
    )


class AttendanceRecord(db.Model):
    """A single student's mark (present/absent/late) within a session.
    Also serves as the running per-course tally (held/attended) used by
    the Subject-Wise Attendance Summary table."""

    __tablename__ = "attendance_records"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("attendance_sessions.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    status = db.Column(db.String(10), nullable=False, default="present")  # present|absent|late

    session = db.relationship("AttendanceSession", back_populates="records")
    student = db.relationship("Student", back_populates="attendance_records")

    __table_args__ = (
        db.CheckConstraint(status.in_(("present", "absent", "late")), name="ck_attendance_status"),
        db.UniqueConstraint("session_id", "student_id", name="uq_record_session_student"),
    )
