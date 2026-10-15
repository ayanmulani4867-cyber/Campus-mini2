# Firebase Realtime Database & Firebase Authentication Migration Guide

This document provides step-by-step instructions to configure Firebase and Render for **Campus-mini2 ERP**.

---

## 1. Firebase Console Configuration

### 1.1 Apply Security Rules & Performance Indexes
1. Go to the [Firebase Console](https://console.firebase.google.com/).
2. Select your project: **Campus-mini2**.
3. In the left navigation menu, go to **Build** → **Realtime Database**.
4. Verify your Database URL is:
   ```
   https://campus-mini2-default-rtdb.firebaseio.com/
   ```
5. Click on the **Rules** tab.
6. Copy the contents of [`database.rules.json`](../database.rules.json) and paste them into the editor:
   ```json
   {
     "rules": {
       ".read": false,
       ".write": false,
       "users": {
         ".indexOn": ["email", "role", "is_active", "phone"]
       },
       "students": {
         ".indexOn": ["user_id", "student_code", "prn", "department_id", "semester", "division", "status"]
       },
       "faculty": {
         ".indexOn": ["user_id", "faculty_code", "department_id", "status"]
       },
       "faculty_assignments": {
         ".indexOn": ["faculty_id", "course_id", "department_id", "semester", "division"]
       },
       "departments": {
         ".indexOn": ["code", "name"]
       },
       "courses": {
         ".indexOn": ["code", "department_id", "semester", "category", "instructor_id", "status"]
       },
       "enrollments": {
         ".indexOn": ["student_id", "course_id"]
       },
       "attendance_sessions": {
         ".indexOn": ["course_id", "marked_by_id", "session_date", "division"]
       },
       "attendance_records": {
         ".indexOn": ["session_id", "student_id", "status"]
       },
       "results": {
         ".indexOn": ["student_id", "course_id", "status", "is_published", "academic_year", "semester", "division"]
       },
       "assessment_configs": {
         ".indexOn": ["course_id", "department_id"]
       },
       "assignments": {
         ".indexOn": ["course_id", "faculty_id", "semester", "division", "due_date"]
       },
       "assignment_submissions": {
         ".indexOn": ["assignment_id", "student_id", "status", "is_locked"]
       },
       "notices": {
         ".indexOn": ["department_id", "posted_by_id", "created_at", "category"]
       },
       "study_materials": {
         ".indexOn": ["course_id", "department_id", "uploaded_by_id", "category"]
       },
       "events": {
         ".indexOn": ["event_date", "category"]
       },
       "leave_requests": {
         ".indexOn": ["student_id", "status", "start_date"]
       },
       "audit_logs": {
         ".indexOn": ["user_id", "action", "created_at"]
       },
       "user_sessions": {
         ".indexOn": ["user_id", "is_active", "role"]
       }
     }
   }
   ```
7. Click **Publish**.

> [!NOTE]
> `.read: false` and `.write: false` completely block unrestricted public access from the internet. The Python backend uses the **Firebase Admin SDK**, which bypasses security rules to securely enforce user authentication and role-based permissions server-side.

---

### 1.2 Enable Firebase Authentication
1. In the Firebase Console, go to **Build** → **Authentication**.
2. Click **Get Started** (if not already enabled).
3. Under the **Sign-in method** tab, click **Email/Password**.
4. Toggle **Enable** on for Email/Password (leave Email link disabled).
5. Click **Save**.

---

### 1.3 Generate Admin Service Account Credentials
1. Click the **Gear icon (Project settings)** at the top left of the Firebase Console.
2. Go to the **Service accounts** tab.
3. Select **Firebase Admin SDK** and choose **Python**.
4. Click **Generate new private key** → click **Generate key** in the confirmation modal.
5. A `.json` file will download to your computer (e.g. `campus-mini2-firebase-adminsdk-xxx.json`).
6. Open the file in VS Code or Notepad:
   - **For local development**: You can rename it to `serviceAccountKey.json` and place it in the project root directory (it is already in `.gitignore`).
   - **For Render**: Copy the entire JSON string to set as an environment variable (see Section 2).

---

## 2. Render Environment Variables

In your [Render Dashboard](https://dashboard.render.com/):
1. Navigate to your **campus-connect** Web Service.
2. In the left menu, select **Environment**.
3. Add / update the following environment variables:

| Variable Name | Value | Description |
| :--- | :--- | :--- |
| `DATABASE_BACKEND` | `firebase` | Configures the application to use Firebase Realtime Database as the primary store. |
| `FIREBASE_DATABASE_URL` | `https://campus-mini2-default-rtdb.firebaseio.com/` | Your Firebase Realtime Database URL. |
| `FIREBASE_SERVICE_ACCOUNT_KEY` | `{"type":"service_account","project_id":"campus-mini2",...}` | Paste the single-line JSON string of your Firebase service account private key. |
| `FLASK_ENV` | `production` | Production environment flag. |
| `SECRET_KEY` | *(Your existing or generated secret)* | Standard Flask session secret. |

> [!IMPORTANT]
> **Free Tier Compliance**: The web service runs entirely within Render's Free Web Service tier (0.5 CPU, 512MB RAM). You do **NOT** need an active paid database.
> **Safety Notice**: Keep your existing PostgreSQL database and `DATABASE_URL` untouched until you have verified the Firebase migration.

---

## 3. Safe, Repeatable Migration Procedure

When you are ready to migrate existing records from PostgreSQL to Firebase:

1. **Test with Dry Run (Safe, Zero-Write)**:
   ```powershell
   python scripts/migrate_postgres_to_firebase.py --dry-run
   ```
   This will:
   - Extract all 18 tables from PostgreSQL.
   - Save a local point-in-time JSON backup file in `scratch/postgres_export_<timestamp>.json`.
   - Print a breakdown of all record counts.
   - Perform **zero** writes to Firebase.

2. **Execute Full Migration**:
   ```powershell
   python scripts/migrate_postgres_to_firebase.py
   ```
   This will:
   - Verify connection to Firebase Realtime Database and Firebase Auth.
   - Save a local JSON backup.
   - Upload all records into Firebase RTDB without overwriting existing entries.
   - Sync all user accounts and roles into Firebase Authentication.
   - Update atomic counters under `/counters/` so future primary keys remain sequential.
   - **Leave the PostgreSQL database completely unmodified and untouched.**

---

## 4. Verification and Testing

Run the migration test suite to verify all workflows:
```powershell
python -m unittest tests/test_firebase_migration.py
```
This suite validates:
1. Firebase Admin SDK service initialization.
2. Firebase RTDB CRUD operations and atomic counters.
3. Health check reporting Firebase configuration.
4. Admin login and department/course management.
5. Faculty attendance roll-call and student attendance summary.
6. Assignment submission and faculty grading workflow.
7. Server-side Firebase ID token verification in `Authorization: Bearer <token>`.
8. `/api/auth/firebase-login` token exchange endpoint.
