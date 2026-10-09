import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import time
import json
from app import create_app
from extensions import db
from sqlalchemy import event
from sqlalchemy.engine import Engine
from models import Assignment, AssignmentSubmission, Course

app = create_app()

query_count = 0

@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    global query_count
    query_count += 1

def measure_endpoint(client, method, url, data=None, headers=None, label=""):
    global query_count
    query_count = 0
    start = time.perf_counter()
    if method == "GET":
        res = client.get(url, headers=headers)
    elif method == "POST":
        res = client.post(url, data=json.dumps(data) if data else None, content_type="application/json", headers=headers)
    elapsed_ms = (time.perf_counter() - start) * 1000
    size_bytes = len(res.data)
    print(f"[{label:38s}] Status: {res.status_code} | Queries: {query_count:3d} | Time: {elapsed_ms:6.1f}ms | Size: {size_bytes:6d}B")
    return {
        "label": label,
        "status": res.status_code,
        "queries": query_count,
        "time_ms": elapsed_ms,
        "size_bytes": size_bytes
    }

def run_benchmarks():
    client = app.test_client()
    results = []

    print("\n" + "="*80)
    print("BASELINE PERFORMANCE BENCHMARKS (MEASURE BEFORE OPTIMIZATION)")
    print("="*80)

    client_student = app.test_client()
    client_faculty = app.test_client()
    client_admin = app.test_client()

    # 1. Login
    res = measure_endpoint(client_student, "POST", "/api/auth/login", {"email": "rahul@campus.edu", "password": "campus@123"}, label="Login (Student)")
    results.append(res)

    # Faculty & Admin login
    client_faculty.post("/api/auth/login", data=json.dumps({"email": "amit.deshmukh@campus.edu", "password": "campus@123"}), content_type="application/json")
    client_admin.post("/api/auth/login", data=json.dumps({"email": "admin@campus.edu", "password": "admin"}), content_type="application/json")

    # 2. Dashboard stats
    results.append(measure_endpoint(client_admin, "GET", "/api/dashboard/stats", label="Dashboard Stats (Admin)"))
    results.append(measure_endpoint(client_faculty, "GET", "/api/dashboard/stats", label="Dashboard Stats (Faculty)"))
    results.append(measure_endpoint(client_student, "GET", "/api/dashboard/stats", label="Dashboard Stats (Student)"))

    # 3. Directory (Admin)
    results.append(measure_endpoint(client_admin, "GET", "/api/students", label="Student Directory (Admin)"))
    results.append(measure_endpoint(client_admin, "GET", "/api/faculty", label="Faculty Directory (Admin)"))

    # 4. Courses
    results.append(measure_endpoint(client_admin, "GET", "/api/courses", label="Courses List"))

    # 5. Attendance
    results.append(measure_endpoint(client_faculty, "GET", "/api/attendance/roll-call?courseCode=CS601&division=A", label="Attendance Roll-Call (Faculty)"))
    results.append(measure_endpoint(client_student, "GET", "/api/attendance/summary", label="Attendance Summary (Student)"))

    # 6. Assignments
    results.append(measure_endpoint(client_student, "GET", "/api/assignments", label="Assignments List (Student)"))
    results.append(measure_endpoint(client_faculty, "GET", "/api/assignments", label="Assignments List (Faculty)"))

    # 7. Assignment Evaluation Roster
    with app.app_context():
        assignment = Assignment.query.first()
        aid = assignment.id if assignment else 1
        sub = AssignmentSubmission.query.filter(AssignmentSubmission.file_data.isnot(None)).first()
        sid = sub.id if sub else 1

    results.append(measure_endpoint(client_faculty, "GET", f"/api/assignments/{aid}/evaluation-roster", label="Assignment Eval Roster (Faculty)"))
    results.append(measure_endpoint(client_faculty, "GET", f"/api/assignments/submissions/{sid}/preview", label="Assignment PDF Preview (Faculty)"))

    # 8. Results
    results.append(measure_endpoint(client_faculty, "GET", "/api/results", label="Results Control / Gradebook (Faculty)"))
    results.append(measure_endpoint(client_student, "GET", "/api/results", label="My Results (Student)"))

    print("="*80 + "\n")
    return results

if __name__ == "__main__":
    run_benchmarks()
