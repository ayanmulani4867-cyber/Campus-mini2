# Campus Connect — College Management System

A college ERP management web portal built with **HTML5, CSS3, Vanilla JavaScript, Python Flask, and PostgreSQL**.

Campus Connect provides role-based workspaces for **Administrators**, **Faculty**, and **Students** to manage college operations, academic tracking, attendance, study materials, examinations, notices, and events.

---

## 1. Technology Stack

- **Frontend**: HTML5, Vanilla CSS3 (custom responsive styling), Vanilla JavaScript (native `fetch` API, no npm / Node build step).
- **Backend**: Python 3.11+, Flask 3.0, Flask-SQLAlchemy, Flask-Migrate (Alembic), Flask-Login, Gunicorn.
- **Database**: PostgreSQL.
- **Architecture**: Single unified Flask application serving both HTML templates / static assets and REST API endpoints.

---

## 2. Directory Structure

```text
CampusConnect/
│
├── app.py                  # Single Flask application entrypoint (Gunicorn target: app:app)
├── config.py               # Centralized configuration (dev/prod, PostgreSQL URLs)
├── extensions.py           # Database & migration extension singletons (db, migrate)
├── seed.py                 # Idempotent database seeder for initial data & demo accounts
├── requirements.txt        # Minimal Python backend dependencies
├── render.yaml             # Single Python Web Service + PostgreSQL database blueprint
├── Procfile                # Production startup command
├── .env.example            # Sample environment variables
├── .gitignore              # Ignores .env, .venv, caches, and temporary files
├── README.md               # Complete architecture & deployment guide
│
├── migrations/             # Alembic / Flask-Migrate database migration scripts
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_baseline_all_tables.py  # Authoritative baseline table creation
│
├── models/                 # Normalized SQLAlchemy database models (17 tables)
│   ├── __init__.py
│   ├── academic.py         # Departments, Courses, Enrollments
│   ├── assignment.py       # Coursework Assignments and Submissions
│   ├── attendance.py       # Attendance sessions and roll-call records
│   ├── content.py          # Notices, Study Materials, Campus Events
│   ├── faculty.py          # Faculty profiles and teaching assignments
│   ├── leave.py            # Student leave requests & approval tracking
│   ├── result.py           # Semester examination marks & grades
│   ├── session.py          # Cryptographic multi-tab user sessions
│   ├── student.py          # Student profiles, PRNs, cohort mappings
│   └── user.py             # User authentication, roles, password hashes
│
├── routes/                 # Flask Blueprints (/api/...)
│   ├── __init__.py
│   ├── assignments.py      # Coursework assignment management & grading
│   ├── attendance.py       # Roll-call rosters & attendance marking
│   ├── auth.py             # Login, logout, session verification, passwords
│   ├── courses.py          # Course directory & semester course scoping
│   ├── dashboard.py        # Dynamic metrics per role (Admin, Faculty, Student)
│   ├── departments.py      # Department directory management
│   ├── events.py           # College events calendar & creation
│   ├── faculty.py          # Faculty directory & class assignment mappings
│   ├── leaves.py           # Leave request application & status approval
│   ├── materials.py        # Upload, filter, and download lecture notes/slides
│   ├── notices.py          # Targeted announcements by cohort & division
│   ├── profile.py          # Self profile viewing and editing
│   ├── results.py          # Grade entry, calculations, and student marksheets
│   └── students.py         # Student directory, PRNs, roll numbers
│
├── services/               # Business logic & storage services
│   ├── __init__.py
│   ├── academic_service.py # Academic mapping & normalization
│   ├── storage.py          # Storage service alias
│   └── storage_service.py  # Validated file uploads (PDF, PPT, PPTX)
│
├── utils/                  # Auth decorators, validators & error handlers
│   ├── __init__.py
│   ├── auth.py             # Multi-tab token isolation & RBAC decorators
│   ├── errors.py           # Uniform JSON error handlers
│   └── validators.py       # Input validation (email, phone, marks)
│
├── templates/              # HTML5 Jinja templates
│   ├── index.html          # Public landing page
│   ├── login.html          # Unified authentication page with role selector
│   ├── dashboard.html      # Responsive workspace dashboard
│   ├── users.html          # User directory (manage Students & Faculty)
│   ├── courses.html        # Enrolled / assigned courses
│   ├── attendance.html     # Attendance roll-call & percentage tracking
│   ├── results.html        # Academic performance & mark entry
│   ├── materials.html      # Upload & download lecture notes / presentations
│   ├── notices.html        # Campus circulars & announcements
│   ├── events.html         # Upcoming events calendar
│   ├── profile.html        # Account profile details
│   ├── settings.html       # Security & password management
│   └── doc.html            # Project presentation / documentation
│
├── static/                 # Static frontend assets served directly by Flask
│   ├── css/
│   │   └── style.css       # Clean, modern CSS styling
│   ├── js/
│   │   ├── app.js          # Client interactions & API fetch handlers
│   │   └── script.js       # Core script alias
│   └── images/
│       └── profile-placeholder.png
│
├── uploads/                # Local uploaded materials storage
│   └── materials/
│
└── tests/                  # Automated integration & verification test suites
    ├── __init__.py
    ├── test_auth_sessions.py  # Multi-tab session isolation & RBAC tests
    └── test_e2e.py            # Comprehensive end-to-end workflow verification
```

---

## 3. Local Setup & Installation

### Step 1: Clone Repository & Create Virtual Environment
```bash
# Clone the repository
git clone <your-repo-url>
cd CampusConnect

# Create Python virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
# Windows:
copy .env.example .env
# Linux/macOS:
cp .env.example .env
```

Edit `.env` to configure your PostgreSQL credentials:
```env
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/campus_connect
SECRET_KEY=your-secure-random-secret-key
FLASK_ENV=development
```

### Step 4: Run Database Migrations
Apply all baseline schema tables to PostgreSQL:
```bash
flask db upgrade
```

### Step 5: Seed Initial Demo Data
Populate departments, courses, students, faculty, notices, and demo accounts:
```bash
python seed.py
```

### Step 6: Start Application
```bash
python app.py
```
Open **`http://127.0.0.1:5000`** in your browser.

---

## 4. Default Demo Accounts

All seeded accounts share the initial password: **`campus@123`**

| Role | Email / Login ID | Password | Access Level |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin@campus.edu` | `campus@123` | Full college admin, User Directory, Add Members |
| **Faculty** | `anita.sen@campus.edu` | `campus@123` | Mark Attendance, Enter Marks, Upload Notes |
| **Student** | `rahul@campus.edu` | `campus@123` | View Attendance %, Results, Download Notes |

*Note: Students and Faculty added by the Admin can also sign in with their registered phone number as their initial temporary password.*

---

## 5. Render Deployment Guide

Deploying Campus Connect on Render requires **ONE single Python Web Service** and **ONE PostgreSQL Database**.

### Method A: Blueprint Deployment (`render.yaml`)
1. Push your repository to GitHub.
2. In the Render Dashboard, go to **Blueprints** and connect your GitHub repository.
3. Render automatically provisions:
   - A managed **PostgreSQL Database** (`campus-connect-db`).
   - A single **Python Web Service** (`campus-connect`).
4. Click **Apply**. Render builds and runs migrations automatically on first boot.

### Method B: Manual Web Service Creation
1. Create a **PostgreSQL** instance on Render and copy its **Internal Database URL**.
2. Create a new **Web Service** on Render connected to your repository:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `flask db upgrade && gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 120 app:app`
3. In **Environment Variables**, add:
   - `DATABASE_URL`: *(paste Internal Database URL)*
   - `SECRET_KEY`: *(click Generate or enter a secure string)*
   - `FLASK_ENV`: `production`
   - `PYTHON_VERSION`: `3.11.0`
4. Click **Deploy Web Service**.

---

## 6. Running Tests

Campus Connect includes automated tests covering multi-tab session isolation, role permissions, and full ERP flows:

```bash
# Run multi-tab authentication & role permission suite
python tests/test_auth_sessions.py

# Run comprehensive end-to-end flow test
python tests/test_e2e.py
```

---

## 7. Troubleshooting

- **`DATABASE_URL` format**: Ensure your PostgreSQL connection string starts with `postgresql://` (or `postgres://`, which `config.py` automatically normalizes).
- **Migration errors on fresh DB**: Run `flask db upgrade`. The baseline migration (`0001_baseline_all_tables.py`) creates all tables in strict foreign-key dependency order.
- **Uploads persistence**: On ephemeral platforms like Render's free tier, local disk files under `uploads/` are reset on container restarts. For high-volume production deployments, mount a persistent disk or set `MATERIAL_UPLOAD_DIR` to a mounted volume path.
