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
    total_points = db.Column(db.Integer, nullable=False, default=10)  # Standardized to 10 marks
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    course = db.relationship("Course", backref=db.backref("assignments", cascade="all, delete-orphan"))
    faculty = db.relationship("Faculty", backref=db.backref("assignments_created", cascade="all, delete-orphan"))
    submissions = db.relationship("AssignmentSubmission", back_populates="assignment", cascade="all, delete-orphan")

    def get_evaluation_counts(self):
        from models import Student, Enrollment
        eligible_q = Student.query.join(Enrollment, Student.id == Enrollment.student_id).filter(
            Enrollment.course_id == self.course_id
        )
        if self.division and self.division.upper() != "ALL":
            eligible_q = eligible_q.filter(
                db.or_(Student.division == self.division, Student.division.is_(None))
            )
        eligible_count = eligible_q.count()
        sub_count = len(self.submissions)
        evaluated_count = sum(1 for s in self.submissions if s.grade is not None or s.status in ("graded", "evaluated"))
        awaiting_count = max(0, sub_count - evaluated_count)
        return {
            "eligibleCount": eligible_count,
            "submissionsCount": sub_count,
            "evaluatedCount": evaluated_count,
            "awaitingEvaluationCount": awaiting_count,
        }

    def to_dict(self, student_id=None, counts=None):
        if counts is None:
            counts = self.get_evaluation_counts()
        stu_sub = None
        if student_id:
            for s in self.submissions:
                if s.student_id == student_id:
                    stu_sub = s.to_dict()
                    break

        is_sub = stu_sub is not None
        is_eval = stu_sub.get("isEvaluated", False) if stu_sub else False
        sub_status = stu_sub.get("status", "not_submitted") if stu_sub else "not_submitted"
        marks_obt = stu_sub.get("grade") if stu_sub else None
        feed = stu_sub.get("feedback") if stu_sub else None

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
            "submissionsCount": counts["submissionsCount"],
            "eligibleCount": counts["eligibleCount"],
            "evaluatedCount": counts["evaluatedCount"],
            "awaitingEvaluationCount": counts["awaitingEvaluationCount"],
            "evaluationCounts": {
                "eligible_students": counts["eligibleCount"],
                "submissions": counts["submissionsCount"],
                "awaiting_evaluation": counts["awaitingEvaluationCount"],
                "evaluated": counts["evaluatedCount"],
            },
            "isSubmitted": is_sub,
            "isEvaluated": is_eval,
            "submissionStatus": sub_status,
            "marksObtained": marks_obt,
            "feedback": feed,
            "submission": stu_sub,
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
    status = db.Column(db.String(20), nullable=False, default="submitted")  # submitted, graded, evaluated, late, under_review
    grade = db.Column(db.Float, nullable=True)
    feedback = db.Column(db.Text, nullable=True)
    graded_by_id = db.Column(db.Integer, db.ForeignKey("faculty.id"), nullable=True)

    __table_args__ = (
        db.UniqueConstraint("assignment_id", "student_id", name="uq_assignment_student"),
        db.CheckConstraint("status IN ('submitted', 'graded', 'evaluated', 'late', 'under_review')", name="ck_submission_status"),
    )

    assignment = db.relationship("Assignment", back_populates="submissions")
    student = db.relationship("Student", backref=db.backref("assignment_submissions", cascade="all, delete-orphan"))
    graded_by = db.relationship("Faculty")

    def to_dict(self):
        stu = self.student
        is_evaluated = self.grade is not None or self.status in ("graded", "evaluated")
        display_status = "Evaluated" if is_evaluated else ("Late Submission" if self.status == "late" else ("Under Review" if self.status == "under_review" else "Submitted"))
        ext = self.file_name.rsplit(".", 1)[-1].lower() if (self.file_name and "." in self.file_name) else ""
        is_pdf = bool(ext == "pdf" or self.mime_type == "application/pdf")
        has_file = bool(self.file_size_bytes or self.file_path or self.file_name)
        return {
            "id": self.id,
            "assignmentId": self.assignment_id,
            "studentId": stu.student_code if stu else None,
            "studentName": stu.user.full_name if (stu and stu.user) else None,
            "prn": stu.prn if stu else (stu.student_code if stu else None),
            "rollNumber": stu.roll_number if stu else None,
            "division": stu.division if stu else None,
            "submissionText": self.submission_text,
            "fileName": self.file_name,
            "fileExtension": ext or None,
            "isPdf": is_pdf,
            "fileSizeBytes": self.file_size_bytes,
            "sizeKb": round(self.file_size_bytes / 1024, 1) if self.file_size_bytes else 0,
            "mimeType": self.mime_type,
            "downloadUrl": f"/api/assignments/{self.assignment_id}/submissions/{self.id}/download" if has_file else None,
            "previewUrl": f"/api/assignments/{self.assignment_id}/submissions/{self.id}/preview" if (has_file and is_pdf) else None,
            "submittedAt": self.submitted_at.isoformat() if self.submitted_at else None,
            "status": "graded" if is_evaluated else self.status,
            "displayStatus": display_status,
            "evaluationStatus": "Evaluated" if is_evaluated else "Awaiting Evaluation",
            "isEvaluated": is_evaluated,
            "grade": self.grade,
            "marks_obtained": self.grade,
            "marks_display": f"{self.grade:g}/10" if self.grade is not None else None,
            "feedback": self.feedback,
            "gradedBy": self.graded_by.user.full_name if (self.graded_by and self.graded_by.user) else None,
        }

