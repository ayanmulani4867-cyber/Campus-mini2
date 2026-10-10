import unittest
from app import create_app
from extensions import db
from models import User, Student, Faculty, Department


class UserDirectoryTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    def login_as(self, email_or_id, password, role="admin"):
        res = self.client.post("/api/auth/login", json={
            "email": email_or_id,
            "password": password,
            "role": role
        })
        token = res.get_json().get("sessionToken") if res.is_json else None
        return res, token

    def test_01_admin_can_access_directory_and_view_students_and_faculty(self):
        """Test that authenticated administrator retrieves real students and faculty."""
        res, token = self.login_as("admin@campus.edu", "admin", "admin")
        self.assertEqual(res.status_code, 200, f"Admin login failed: {res.data}")
        headers = {"X-Session-Token": token}

        # 1. Fetch user directory
        res = self.client.get("/api/users", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        items = data["data"]

        # Confirm both students and faculty are present
        roles_present = {u["role"] for u in items}
        self.assertIn("student", roles_present, "Directory must contain student records")
        self.assertIn("faculty", roles_present, "Directory must contain faculty records")
        self.assertIn("admin", roles_present, "Directory must contain admin records")

        # Verify no secret fields are exposed
        for u in items:
            self.assertNotIn("password_hash", u)
            self.assertNotIn("password", u)
            self.assertNotIn("token", u)
            self.assertIn("name", u)
            self.assertIn("email", u)
            self.assertIn("role", u)

        # Verify stats and pagination
        self.assertIn("pagination", data)
        self.assertGreaterEqual(data["pagination"]["total"], 5)
        self.assertIn("stats", data)
        self.assertIn("totalDepartments", data["stats"])
        self.assertGreaterEqual(data["stats"]["totalStudents"], 2)
        self.assertGreaterEqual(data["stats"]["totalFaculty"], 3)

    def test_02_users_filters_endpoint(self):
        """Test /api/users/filters returns department, role options, and counts."""
        res, token = self.login_as("admin@campus.edu", "admin", "admin")
        self.assertEqual(res.status_code, 200)
        headers = {"X-Session-Token": token}

        res = self.client.get("/api/users/filters", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("departments", data)
        self.assertIn("roles", data)
        self.assertIn("stats", data)
        self.assertIn("totalDepartments", data["stats"])
        self.assertGreaterEqual(len(data["departments"]), 4)

    def test_03_search_functionality(self):
        """Test searching by student name, roll number, PRN, faculty code, and email."""
        res, token = self.login_as("admin@campus.edu", "admin", "admin")
        self.assertEqual(res.status_code, 200)
        headers = {"X-Session-Token": token}

        # Search by student name
        res = self.client.get("/api/users?q=Aarav", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()["data"]
        self.assertTrue(any("Aarav" in u["name"] for u in data))

        # Search by roll number
        res = self.client.get("/api/users?q=42", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()["data"]
        self.assertTrue(any(u.get("rollNumber") == "42" for u in data))

        # Search by PRN
        res = self.client.get("/api/users?q=24101005", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()["data"]
        self.assertTrue(any("24101005" in (u.get("prn") or "") for u in data))

        # Search by faculty code
        res = self.client.get("/api/users?q=FAC2026001", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()["data"]
        self.assertTrue(any("FAC2026001" in (u.get("publicId") or "") for u in data))

        # Search by faculty name
        res = self.client.get("/api/users?q=Rahul", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()["data"]
        self.assertTrue(any("Rahul" in u["name"] for u in data))

    def test_04_role_and_department_filters(self):
        """Test filtering by role and department."""
        res, token = self.login_as("admin@campus.edu", "admin", "admin")
        self.assertEqual(res.status_code, 200)
        headers = {"X-Session-Token": token}

        # Role filter: student
        res = self.client.get("/api/users?role=student", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()["data"]
        self.assertTrue(all(u["role"] == "student" for u in data))
        self.assertGreaterEqual(len(data), 2)

        # Role filter: faculty
        res = self.client.get("/api/users?role=faculty", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()["data"]
        self.assertTrue(all(u["role"] == "faculty" for u in data))
        self.assertGreaterEqual(len(data), 3)

        # Department filter: CSE
        res = self.client.get("/api/users?department=CSE", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()["data"]
        self.assertTrue(all("Computer Science" in (u.get("department") or "") or u.get("departmentCode") == "CSE" for u in data))

        # Combined filter: student + CSE
        res = self.client.get("/api/users?role=student&department=CSE", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()["data"]
        self.assertTrue(all(u["role"] == "student" for u in data))
        self.assertGreaterEqual(len(data), 2)

    def test_05_unauthorized_user_cannot_access_directory(self):
        """Verify unauthorized users (student and unauthenticated) cannot access admin directory."""
        # Unauthenticated request
        res = self.client.get("/api/users")
        self.assertEqual(res.status_code, 401)

        res = self.client.get("/api/users/filters")
        self.assertEqual(res.status_code, 401)

        # Student user attempting to access admin directory
        res, stu_token = self.login_as("student.test@sitcoe.ac.in", "student123", "student")
        self.assertEqual(res.status_code, 200)
        stu_headers = {"X-Session-Token": stu_token}

        res = self.client.get("/api/users", headers=stu_headers)
        self.assertEqual(res.status_code, 403, "Student must receive 403 Forbidden for /api/users")

        res = self.client.get("/api/users/filters", headers=stu_headers)
        self.assertEqual(res.status_code, 403, "Student must receive 403 Forbidden for /api/users/filters")

    def test_06_user_detail_endpoint(self):
        """Test /api/users/<user_id> returns complete member profile."""
        res, token = self.login_as("admin@campus.edu", "admin", "admin")
        self.assertEqual(res.status_code, 200)
        headers = {"X-Session-Token": token}

        # Admin user detail
        res = self.client.get("/api/users/1", headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["data"]["role"], "admin")

        # Student user detail
        res = self.client.get("/api/users/45", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()["data"]
        self.assertEqual(data["role"], "student")
        self.assertIn("enrolledCourses", data)

        # Faculty user detail
        res = self.client.get("/api/users/43", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()["data"]
        self.assertEqual(data["role"], "faculty")
        self.assertIn("subjectAssignments", data)


if __name__ == "__main__":
    unittest.main()
