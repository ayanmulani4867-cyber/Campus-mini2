from extensions import db


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    student_code = db.Column(db.String(30), unique=True, nullable=False)  # STU2024001
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False)
    year_label = db.Column(db.String(20), nullable=False, default="1st Year")  # "3rd Year"
    semester = db.Column(db.Integer, nullable=False, default=1)
    division = db.Column(db.String(10), nullable=False, default="A")  # "A", "B", etc.
    roll_number = db.Column(db.String(30), nullable=True)  # e.g. "32"
    prn = db.Column(db.String(50), nullable=True)  # Student ID / PRN
    status = db.Column(db.String(20), nullable=False, default="active")

    user = db.relationship("User", back_populates="student_profile")
    department = db.relationship("Department", back_populates="students")
    enrollments = db.relationship(
        "Enrollment", back_populates="student", cascade="all, delete-orphan"
    )
    attendance_records = db.relationship(
        "AttendanceRecord", back_populates="student", cascade="all, delete-orphan"
    )
    results = db.relationship("Result", back_populates="student", cascade="all, delete-orphan")

    def to_profile_dict(self):
        return {
            "dept": self.department.name if self.department else None,
            "departmentId": self.department_id,
            "year": self.year_label,
            "semester": f"{self.semester}{'th' if self.semester not in (1,2,3) else ('st' if self.semester==1 else 'nd' if self.semester==2 else 'rd')} Semester",
            "division": self.division or "A",
            "rollNumber": self.roll_number,
            "prn": self.prn or self.student_code,
        }

    def to_dict(self):
        return {
            "id": self.student_code,
            "studentCode": self.student_code,
            "prn": self.prn or self.student_code,
            "name": self.user.full_name,
            "email": self.user.email,
            "phone": self.user.phone,
            "dept": self.department.name if self.department else None,
            "departmentId": self.department_id,
            "year": self.year_label,
            "semester": self.semester,
            "division": self.division or "A",
            "rollNumber": self.roll_number,
            "status": self.status,
        }
