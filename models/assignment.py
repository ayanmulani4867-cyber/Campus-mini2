from datetime import datetime, timezone
from extensions import db


class Assignment(db.Model):
    __tablename__ = "assignments"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey("faculty.id"), nullable=False)
    year_label = db.Column(db.String(20), nullable=True)
    semester = db.Column(db.Integer, nullable=True)
    division = db.Column(db.String(10), nullable=True, default="All")
    due_date = db.Column(db.DateTime, nullable=False)
    total_points = db.Column(db.Integer, nullable=False, default=100)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    course = db.relationship("Course", backref=db.backref("assignments", cascade="all, delete-orphan"))
    faculty = db.relationship("Faculty", backref=db.backref("assignments_created", cascade="all, delete-orphan"))
    submissions = db.relationship("AssignmentSubmission", back_populates="assignment", cascade="all, delete-orphan")

    def to_dict(self, student_id=None):
        sub_count = len(self.submissions)
        stu_sub = None
        if student_id:
            for s in self.submissions:
                if s.student_id == student_id:
                    stu_sub = s.to_dict()
                    break

        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "courseId": self.course_id,
            "courseCode": self.course.code if self.course else None,
            "courseTitle": self.course.title if self.course else None,
            "facultyId": self.faculty.faculty_code if self.faculty else None,
            "facultyName": self.faculty.user.full_name if (self.faculty and self.faculty.user) else None,
            "year": self.year_label,
            "semester": self.semester,
            "division": self.division,
            "dueDate": self.due_date.isoformat() if self.due_date else None,
            "totalPoints": self.total_points,
            "submissionsCount": sub_count,
            "mySubmission": stu_sub,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class AssignmentSubmission(db.Model):
    __tablename__ = "assignment_submissions"

    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    submission_text = db.Column(db.Text, nullable=True)
    file_path = db.Column(db.String(500), nullable=True)
    file_name = db.Column(db.String(255), nullable=True)
    file_data = db.Column(db.LargeBinary, nullable=True)  # PostgreSQL BYTEA persistent storage
    file_size_bytes = db.Column(db.Integer, nullable=False, default=0)
    mime_type = db.Column(db.String(150), nullable=True)
    submitted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.String(20), nullable=False, default="submitted")  # submitted, graded, late
    grade = db.Column(db.Float, nullable=True)
    feedback = db.Column(db.Text, nullable=True)
    graded_by_id = db.Column(db.Integer, db.ForeignKey("faculty.id"), nullable=True)

    __table_args__ = (
        db.UniqueConstraint("assignment_id", "student_id", name="uq_assignment_student"),
        db.CheckConstraint("status IN ('submitted', 'graded', 'late')", name="ck_submission_status"),
    )

    assignment = db.relationship("Assignment", back_populates="submissions")
    student = db.relationship("Student", backref=db.backref("assignment_submissions", cascade="all, delete-orphan"))
    graded_by = db.relationship("Faculty")

    def to_dict(self):
        stu = self.student
        return {
            "id": self.id,
            "assignmentId": self.assignment_id,
            "studentId": stu.student_code if stu else None,
            "studentName": stu.user.full_name if (stu and stu.user) else None,
            "prn": stu.prn if stu else None,
            "division": stu.division if stu else None,
            "submissionText": self.submission_text,
            "fileName": self.file_name,
            "fileSizeBytes": self.file_size_bytes,
            "sizeKb": round(self.file_size_bytes / 1024, 1) if self.file_size_bytes else 0,
            "mimeType": self.mime_type,
            "downloadUrl": f"/api/assignments/{self.assignment_id}/submissions/{self.id}/download" if (self.file_data or self.file_path) else None,
            "submittedAt": self.submitted_at.isoformat() if self.submitted_at else None,
            "status": self.status,
            "grade": self.grade,
            "marks_obtained": self.grade,
            "feedback": self.feedback,
            "gradedBy": self.graded_by.user.full_name if (self.graded_by and self.graded_by.user) else None,
        }
