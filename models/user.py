from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db

ROLES = ("admin", "faculty", "student")


class User(db.Model):
    """Core authentication record. One row per human, regardless of role.
    Role-specific profile data lives in Student / Faculty."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(20), nullable=True, index=True)
    role = db.Column(db.String(20), nullable=False)  # admin | faculty | student
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    student_profile = db.relationship(
        "Student", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    faculty_profile = db.relationship(
        "Faculty", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        db.CheckConstraint(role.in_(ROLES), name="ck_users_role_valid"),
    )

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    @property
    def role_label(self):
        return {"admin": "Administrator", "faculty": "Faculty", "student": "Student"}.get(
            self.role, self.role
        )

    @property
    def public_id(self):
        """The human-facing ID shown in the UI (STU2024001 / FAC2018042 / ADM..)."""
        if self.student_profile:
            return self.student_profile.student_code
        if self.faculty_profile:
            return self.faculty_profile.faculty_code
        return "ADM" + str(self.id).zfill(6)

    def to_dict(self):
        data = {
            "id": self.id,
            "email": self.email,
            "name": self.full_name,
            "phone": self.phone,
            "role": self.role,
            "roleLabel": self.role_label,
            "publicId": self.public_id,
            "isActive": self.is_active,
        }
        if self.student_profile:
            data.update(self.student_profile.to_profile_dict())
        elif self.faculty_profile:
            data.update(self.faculty_profile.to_profile_dict())
        return data

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"
