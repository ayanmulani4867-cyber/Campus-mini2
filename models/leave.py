from datetime import datetime, timezone, date
from extensions import db


class LeaveRequest(db.Model):
    __tablename__ = "leave_requests"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    leave_type = db.Column(db.String(50), nullable=False, default="Personal")  # Medical, Personal, Academic, On Duty
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")  # pending, approved, rejected
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    review_remarks = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        db.CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_leave_status"),
    )

    student = db.relationship("Student", backref=db.backref("leave_requests", cascade="all, delete-orphan"))
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id])

    def to_dict(self):
        stu = self.student
        return {
            "id": self.id,
            "studentId": stu.student_code if stu else None,
            "studentName": stu.user.full_name if (stu and stu.user) else None,
            "prn": stu.prn if stu else None,
            "department": stu.department.name if (stu and stu.department) else None,
            "division": stu.division if stu else None,
            "leaveType": self.leave_type,
            "startDate": self.start_date.isoformat() if self.start_date else None,
            "endDate": self.end_date.isoformat() if self.end_date else None,
            "reason": self.reason,
            "status": self.status,
            "reviewedBy": self.reviewed_by.full_name if self.reviewed_by else None,
            "reviewRemarks": self.review_remarks,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
