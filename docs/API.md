# Campus Connect REST API Specification

Campus Connect provides a modular, RESTful API partitioned into 12 core blueprints. All responses use JSON format with standard HTTP status codes.

---

## Authentication & Headers

| Header | Format | Description |
|---|---|---|
| `Content-Type` | `application/json` | Required for JSON request payloads. |
| `X-Session-Token` | `<string>` | Multi-tab isolated session token returned by `/api/auth/login`. |

Standard error response format:
```json
{
  "success": false,
  "error": "Descriptive error message"
}
```

---

## 1. Authentication Blueprint (`/api/auth`)

### `POST /api/auth/login`
Authenticates a user and returns a unique session token for multi-tab isolation.
- **Request Body**:
  ```json
  {
    "email": "admin@campus.edu",
    "password": "campus@123",
    "role": "admin"
  }
  ```
- **Success (200 OK)**:
  ```json
  {
    "success": true,
    "sessionToken": "d4f8...",
    "data": {
      "id": 1,
      "email": "admin@campus.edu",
      "fullName": "Admin Controller",
      "role": "admin"
    }
  }
  ```

### `POST /api/auth/logout`
Revokes the current session token without affecting other active browser tabs.
- **Success (200 OK)**: `{"success": true, "message": "Logged out"}`

### `GET /api/auth/me`
Retrieves currently authenticated user information and profile details.
- **Success (200 OK)**:
  ```json
  {
    "success": true,
    "data": {
      "id": 1,
      "email": "rahul@campus.edu",
      "fullName": "John Snow",
      "role": "student",
      "department": "Computer Science & Engineering",
      "year": "3rd Year",
      "semester": 6,
      "division": "A",
      "studentCode": "STU2024001"
    }
  }
  ```

### `POST /api/auth/change-password`
Changes the user's password.
- **Request Body**:
  ```json
  {
    "oldPassword": "currentPassword123",
    "newPassword": "newSecurePassword456"
  }
  ```

---

## 2. Students Blueprint (`/api/students`)

- `GET /api/students`: List students (supports `?department=`, `?year=`, `?division=`, `?search=`).
- `GET /api/students/<student_code_or_prn>`: Get individual student profile.
- `POST /api/students`: Create new student member (Admin only).
  ```json
  {
    "name": "Rahul Sharma",
    "email": "rahul.s@campus.edu",
    "phone": "9876543210",
    "department": "Computer Science & Engineering",
    "year": "3rd Year",
    "semester": 6,
    "division": "A",
    "prn": "PRN2024999"
  }
  ```
- `PUT /api/students/<student_code_or_prn>`: Update student details.
- `DELETE /api/students/<student_code_or_prn>`: Delete student account and associations.

---

## 3. Faculty Blueprint (`/api/faculty`)

- `GET /api/faculty`: List faculty members with teaching assignments.
- `GET /api/faculty/<id_or_code>`: Get faculty profile and assigned courses.
- `POST /api/faculty`: Add new faculty member with assignments (Admin only).
- `PUT /api/faculty/<id_or_code>`: Update faculty profile and designations.
- `DELETE /api/faculty/<id_or_code>`: Delete faculty member.

---

## 4. Academic Blueprints (`/api/departments`, `/api/courses`)

- `GET /api/departments`: List all academic departments.
- `POST /api/departments`: Create department (Admin only).
- `GET /api/courses`: List courses with instructor and coverage details.
- `POST /api/courses`: Create course (Admin only).
- `GET /api/courses/<id>`: Get specific course information.

---

## 5. Attendance Blueprint (`/api/attendance`)

- `GET /api/attendance/summary`: Get student attendance metrics and session percentage.
- `GET /api/attendance/roll-call?courseCode=CS601&division=A`: Retrieve classroom roster for roll call.
- `POST /api/attendance/roll-call`: Submit roll-call records for course/division.
  ```json
  {
    "courseCode": "CS601",
    "division": "A",
    "records": [
      {"studentId": "STU2024001", "status": "present"},
      {"studentId": "STU2024002", "status": "absent"}
    ]
  }
  ```

---

## 6. Results & Marks Blueprint (`/api/results`)

- `GET /api/results`: Retrieve marks and grade reports (scoped to role).
- `POST /api/results`: Record/update marks for a student course.
  ```json
  {
    "studentId": "STU2024001",
    "courseCode": "CS601",
    "marks": 82
  }
  ```
- `PUT /api/results/<id>/publish`: Toggle published status (`{"isPublished": true}`).

---

## 7. Study Repository Blueprint (`/api/materials`)

- `GET /api/materials`: Filtered materials (PDF, PPT, PPTX) matching student cohort or faculty courses.
- `POST /api/materials`: Multipart file upload (Title, category, courseCode, department, year, semester, division, file).
- `GET /api/materials/<id>/download`: Stream and download material file with role verification.
- `DELETE /api/materials/<id>`: Delete material and remove file from storage.

---

## 8. Notices Blueprint (`/api/notices`)

- `GET /api/notices`: Fetch active notices.
- `POST /api/notices`: Publish notice broadcast (Admin / Faculty).
- `DELETE /api/notices/<id>`: Delete notice.

---

## 9. Events Blueprint (`/api/events`)

- `GET /api/events`: Fetch upcoming campus events.
- `POST /api/events`: Create campus event (Admin / Faculty).
- `POST /api/events/<id>/register`: Register for event.
- `DELETE /api/events/<id>`: Delete campus event.

---

## 10. Dashboard Blueprint (`/api/dashboard`)

- `GET /api/dashboard/summary`: High-level counters, attendance stats, and recent activities tailored to the user's role.

---

## 11. Health Check Endpoint (`/api/health`)

- `GET /api/health`: Uptime and database connectivity status check.
  ```json
  {
    "success": true,
    "status": "ok",
    "environment": "production",
    "databaseConfigured": true
  }
  ```
