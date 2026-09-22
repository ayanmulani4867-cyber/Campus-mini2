from models import Department, Course, FacultyAssignment


class AcademicService:
    """Helper services for academic mapping:
    Department -> Year -> Semester -> Division -> Course -> Faculty Assignment -> Student Enrollment.
    """

    YEAR_SEMESTER_MAP = {
        1: "1st Year",
        2: "1st Year",
        3: "2nd Year",
        4: "2nd Year",
        5: "3rd Year",
        6: "3rd Year",
        7: "4th Year",
        8: "4th Year",
    }

    @classmethod
    def get_year_label_for_semester(cls, semester: int) -> str:
        try:
            return cls.YEAR_SEMESTER_MAP.get(int(semester), "1st Year")
        except (ValueError, TypeError):
            return "1st Year"

    @classmethod
    def normalize_division(cls, division: str) -> str:
        div = (division or "A").strip()
        return "All" if div.lower() == "all" else div.upper()


academic_service = AcademicService()
