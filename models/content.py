from datetime import datetime, timezone
from extensions import db


class Notice(db.Model):
    __tablename__ = "notices"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(40), nullable=False, default="General")
    body = db.Column(db.Text, nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=True)
    year_label = db.Column(db.String(20), nullable=True)  # e.g. "3rd Year" or None for all
    semester = db.Column(db.Integer, nullable=True)  # e.g. 5 or None for all
    division = db.Column(db.String(10), nullable=True, default="All")  # "All", "A", "B", etc.
    posted_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    posted_by = db.relationship("User")
    department = db.relationship("Department")

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "body": self.body,
            "department": self.department.name if self.department else "All Departments",
            "departmentId": self.department_id,
            "year": self.year_label or "All Years",
            "semester": self.semester,
            "division": self.division or "All",
            "postedBy": self.posted_by.full_name if self.posted_by else None,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class StudyMaterial(db.Model):
    __tablename__ = "study_materials"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(40), nullable=False, default="Notes")
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=True)
    year_label = db.Column(db.String(20), nullable=True)
    semester = db.Column(db.Integer, nullable=True)
    division = db.Column(db.String(10), nullable=True, default="All")
    file_name = db.Column(db.String(255), nullable=False)
    file_size_bytes = db.Column(db.Integer, nullable=False, default=0)
    file_path = db.Column(db.String(500), nullable=True)
    file_data = db.Column(db.LargeBinary, nullable=True)  # PostgreSQL BYTEA persistent storage
    mime_type = db.Column(db.String(150), nullable=True)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    course = db.relationship("Course")
    department = db.relationship("Department")
    uploaded_by = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "subject": self.course.title if self.course else None,
            "courseCode": self.course.code if self.course else None,
            "department": self.department.name if self.department else (self.course.department.name if self.course and self.course.department else "All"),
            "departmentId": self.department_id or (self.course.department_id if self.course else None),
            "year": self.year_label,
            "semester": self.semester or (self.course.semester if self.course else None),
            "division": self.division or "All",
            "fileName": self.file_name,
            "downloadUrl": f"/api/materials/{self.id}/download" if (self.file_data or self.file_path) else None,
            "mimeType": self.mime_type,
            "sizeKb": round(self.file_size_bytes / 1024, 1),
            "uploadedBy": self.uploaded_by.full_name if self.uploaded_by else None,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class Event(db.Model):
    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(40), nullable=False, default="General")
    event_date = db.Column(db.Date, nullable=False)
    location = db.Column(db.String(150))
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    created_by = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "date": self.event_date.isoformat() if self.event_date else None,
            "location": self.location,
            "createdBy": self.created_by.full_name if self.created_by else None,
        }
