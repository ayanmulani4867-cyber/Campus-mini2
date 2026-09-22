# Campus Connect Database Architecture & Schema

Campus Connect utilizes **PostgreSQL** with **SQLAlchemy ORM** and **Flask-Migrate (Alembic)** for production-grade schema management.

---

## Academic Hierarchy Mapping

The relational schema implements the following strict academic hierarchy:

```
Department (e.g. Computer Science & Engineering)
  └── Academic Year (e.g. 3rd Year)
        └── Semester (e.g. Semester 6)
              └── Division (e.g. Division A / Division B / All)
                    ├── Courses (e.g. CS601 Database Management Systems)
                    │     ├── Faculty Assignments (Instructor -> Course -> Semester -> Division)
                    │     └── Student Enrollments (Student -> Course)
                    ├── Study Materials (Scoped to Dept, Year, Sem, Division)
                    ├── Attendance Sessions & Records (Course, Faculty, Date, Division)
                    └── Results & Scorecards (Student, Course, Internal, End-Sem, Grade)
```

---

## Core Tables & Schema Definitions

### 1. `users`
- `id` (SERIAL PRIMARY KEY)
- `email` (VARCHAR(120) UNIQUE NOT NULL)
- `password_hash` (VARCHAR(256) NOT NULL)
- `full_name` (VARCHAR(120) NOT NULL)
- `role` (VARCHAR(20) NOT NULL) -- `'admin'`, `'faculty'`, `'student'`
- `phone` (VARCHAR(20))
- `created_at` (TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP)

### 2. `user_sessions`
- `id` (SERIAL PRIMARY KEY)
- `token` (VARCHAR(64) UNIQUE NOT NULL INDEX)
- `user_id` (INTEGER REFERENCES users(id) ON DELETE CASCADE)
- `created_at` (TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP)
- `expires_at` (TIMESTAMP WITH TIME ZONE NOT NULL)

### 3. `departments`
- `id` (SERIAL PRIMARY KEY)
- `code` (VARCHAR(10) UNIQUE NOT NULL)
- `name` (VARCHAR(120) NOT NULL)

### 4. `courses`
- `id` (SERIAL PRIMARY KEY)
- `code` (VARCHAR(20) UNIQUE NOT NULL)
- `title` (VARCHAR(150) NOT NULL)
- `credits` (INTEGER NOT NULL DEFAULT 3)
- `category` (VARCHAR(50) DEFAULT 'core')
- `semester` (INTEGER NOT NULL DEFAULT 1)
- `room` (VARCHAR(50))
- `syllabus_coverage` (INTEGER DEFAULT 0)
- `department_id` (INTEGER REFERENCES departments(id))
- `instructor_id` (INTEGER REFERENCES faculty(id))

### 5. `faculty` & `faculty_assignments`
- `faculty.id` (SERIAL PRIMARY KEY)
- `faculty.user_id` (INTEGER UNIQUE REFERENCES users(id) ON DELETE CASCADE)
- `faculty.faculty_code` (VARCHAR(30) UNIQUE NOT NULL)
- `faculty.department_id` (INTEGER REFERENCES departments(id))
- `faculty.designation` (VARCHAR(80))
- `faculty_assignments`: Relational mapping of faculty teaching assignments:
  - `faculty_id`, `course_id`, `department_id`, `year_label`, `semester`, `division`
  - UNIQUE constraint on `(faculty_id, course_id, semester, division)`.

### 6. `students` & `enrollments`
- `students.id` (SERIAL PRIMARY KEY)
- `students.user_id` (INTEGER UNIQUE REFERENCES users(id) ON DELETE CASCADE)
- `students.student_code` (VARCHAR(30) UNIQUE NOT NULL)
- `students.department_id` (INTEGER REFERENCES departments(id))
- `students.year_label` (VARCHAR(20) NOT NULL DEFAULT '1st Year')
- `students.semester` (INTEGER NOT NULL DEFAULT 1)
- `students.division` (VARCHAR(10) NOT NULL DEFAULT 'A')
- `students.roll_number` (VARCHAR(30))
- `students.prn` (VARCHAR(50))
- `enrollments`: Many-to-many relationship between `students` and `courses`.

### 7. `attendance_sessions` & `attendance_records`
- `attendance_sessions`: `course_id`, `faculty_id`, `session_date`, `time_slot`, `topic`, `division`.
- `attendance_records`: `session_id`, `student_id`, `status` (`'present'`, `'absent'`, `'late'`).

### 8. `results`
- `id` (SERIAL PRIMARY KEY)
- `student_id` (INTEGER REFERENCES students(id) ON DELETE CASCADE)
- `course_id` (INTEGER REFERENCES courses(id) ON DELETE CASCADE)
- `internal_marks` (FLOAT DEFAULT 0.0)
- `end_sem_marks` (FLOAT DEFAULT 0.0)
- `assessment_type` (VARCHAR(50) DEFAULT 'Semester Exam')
- `is_published` (BOOLEAN DEFAULT FALSE)
- `entered_by_id` (INTEGER REFERENCES faculty(id))

### 9. `study_materials`
- `id` (SERIAL PRIMARY KEY)
- `title` (VARCHAR(200) NOT NULL)
- `category` (VARCHAR(50) DEFAULT 'Notes')
- `course_id` (INTEGER REFERENCES courses(id))
- `department_id` (INTEGER REFERENCES departments(id))
- `year_label` (VARCHAR(20))
- `semester` (INTEGER)
- `division` (VARCHAR(10) DEFAULT 'All')
- `file_name` (VARCHAR(255) NOT NULL)
- `file_size_bytes` (INTEGER DEFAULT 0)
- `file_path` (VARCHAR(500) NOT NULL)
- `mime_type` (VARCHAR(150))
- `uploaded_by_id` (INTEGER REFERENCES users(id))
- `created_at` (TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP)

### 10. `leave_requests`
- `id` (SERIAL PRIMARY KEY)
- `student_id` (INTEGER REFERENCES students(id) NOT NULL)
- `leave_type` (VARCHAR(50) DEFAULT 'Personal')
- `start_date` (DATE NOT NULL)
- `end_date` (DATE NOT NULL)
- `reason` (TEXT NOT NULL)
- `status` (VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')))
- `reviewed_by_id` (INTEGER REFERENCES users(id))
- `review_remarks` (TEXT)
- `created_at` (TIMESTAMP)
- `updated_at` (TIMESTAMP)

### 11. `assignments`
- `id` (SERIAL PRIMARY KEY)
- `title` (VARCHAR(200) NOT NULL)
- `description` (TEXT)
- `course_id` (INTEGER REFERENCES courses(id) NOT NULL)
- `faculty_id` (INTEGER REFERENCES faculty(id) NOT NULL)
- `year_label` (VARCHAR(20))
- `semester` (INTEGER)
- `division` (VARCHAR(10) DEFAULT 'All')
- `due_date` (TIMESTAMP NOT NULL)
- `total_points` (INTEGER DEFAULT 100)
- `created_at` (TIMESTAMP)

### 12. `assignment_submissions`
- `id` (SERIAL PRIMARY KEY)
- `assignment_id` (INTEGER REFERENCES assignments(id) ON DELETE CASCADE NOT NULL)
- `student_id` (INTEGER REFERENCES students(id) ON DELETE CASCADE NOT NULL)
- `submission_text` (TEXT)
- `file_path` (VARCHAR(500))
- `file_name` (VARCHAR(255))
- `submitted_at` (TIMESTAMP)
- `status` (VARCHAR(20) DEFAULT 'submitted' CHECK (status IN ('submitted', 'graded', 'late')))
- `grade` (FLOAT)
- `feedback` (TEXT)
- `graded_by_id` (INTEGER REFERENCES faculty(id))
- UNIQUE (`assignment_id`, `student_id`)

---

## Database Commands

### Apply Migrations
```bash
flask db upgrade
```

### Create New Migration
```bash
flask db migrate -m "describe changes"
```

### Seed Demo Data
```bash
python seed.py
```
