import re
from datetime import date

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[0-9+\-\s]{7,15}$")


class ValidationError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


def require_fields(data: dict, fields: list):
    missing = [f for f in fields if data.get(f) in (None, "", [])]
    if missing:
        raise ValidationError(f"Missing required field(s): {', '.join(missing)}")


def validate_email(value: str):
    if not value or not EMAIL_RE.match(value):
        raise ValidationError("Invalid email address.")
    return value.strip().lower()


def validate_phone(value: str):
    if value and not PHONE_RE.match(value):
        raise ValidationError("Invalid phone number.")
    return value


def validate_role(value: str):
    if value not in ("admin", "faculty", "student"):
        raise ValidationError("Role must be one of: admin, faculty, student.")
    return value


def validate_date(value: str):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValidationError("Invalid date, expected YYYY-MM-DD.")


def validate_marks(value, minimum, maximum, label="marks"):
    try:
        num = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"Invalid {label}: must be a number.")
    if num < minimum or num > maximum:
        raise ValidationError(f"Invalid {label}: must be between {minimum} and {maximum}.")
    return num
