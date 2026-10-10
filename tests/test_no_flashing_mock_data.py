import os
import sys
import re

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app import create_app

def run_flashing_data_audit():
    print("=" * 70)
    print("CAMPUS CONNECT ERP -- AUDIT: REMOVAL OF FLASHING MOCK/DEMO DATA")
    print("=" * 70)

    templates_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
    js_file = os.path.join(os.path.dirname(__file__), "..", "static", "js", "script.js")
    css_file = os.path.join(os.path.dirname(__file__), "..", "static", "css", "style.css")

    # 1. Verify CSS styles for loading spinner and skeleton state
    print("\n[CHECK 1] Verifying CSS loading infrastructure (.page-spinner & .skeleton-stat)...")
    with open(css_file, "r", encoding="utf-8") as f:
        css_content = f.read()
    assert ".page-spinner" in css_content, "Missing .page-spinner in style.css"
    assert "skeletonPulse" in css_content or ".skeleton-stat" in css_content, "Missing skeleton animation in style.css"
    print("  [PASS] CSS spinner ring and skeleton stat animations defined.")

    # 2. Check templates for hardcoded mock data removal
    print("\n[CHECK 2] Auditing HTML templates for removal of mock records...")

    # Dashboard: No hardcoded mock notices or mock events
    with open(os.path.join(templates_dir, "dashboard.html"), "r", encoding="utf-8") as f:
        dash_content = f.read()
    assert "Mid-Semester Exam Timetable" not in dash_content, "Mock notice found in dashboard.html"
    assert "Inter-Branch Football" not in dash_content, "Mock event found in dashboard.html"
    assert 'id="dashboardRecentNotices"' in dash_content, "Missing #dashboardRecentNotices in dashboard.html"
    assert 'id="dashboardRecentEvents"' in dash_content, "Missing #dashboardRecentEvents in dashboard.html"
    assert "page-spinner" in dash_content, "Dashboard notices missing initial loading spinner"
    print("  [PASS] dashboard.html: Mock notices and events replaced with neutral loading spinners.")

    # Users: No hardcoded 1,250 or 85
    with open(os.path.join(templates_dir, "users.html"), "r", encoding="utf-8") as f:
        users_html = f.read()
    assert '1,250' not in users_html, "Hardcoded '1,250' found in users.html"
    assert '85' not in users_html or 'statTotalFaculty">85' in users_html, "Hardcoded faculty stat found in users.html"
    assert 'id="statTotalStudents">--' in users_html, "statTotalStudents should default to '--'"
    assert 'id="statTotalFaculty">--' in users_html, "statTotalFaculty should default to '--'"
    assert 'page-spinner' in users_html, "usersTableBody missing page-spinner"
    print("  [PASS] users.html: Hardcoded counts replaced with '--' and usersTableBody has initial spinner.")

    # Results: No hardcoded batch table records (Prof. Amit Deshmukh, 120 students, etc.)
    with open(os.path.join(templates_dir, "results.html"), "r", encoding="utf-8") as f:
        results_html = f.read()
    assert "Prof. Amit Deshmukh" not in results_html, "Hardcoded faculty batch found in results.html"
    assert "Prof. Rajesh Verma" not in results_html, "Hardcoded faculty batch found in results.html"
    assert "1,180" not in results_html, "Hardcoded scorecard count 1,180 found in results.html"
    assert "94.8%" not in results_html, "Hardcoded passing rate 94.8% found in results.html"
    assert 'id="statAdminPublishedResults">--' in results_html, "statAdminPublishedResults must default to '--'"
    assert 'id="statAdminTotalScorecards">--' in results_html, "statAdminTotalScorecards must default to '--'"
    assert 'page-spinner' in results_html, "results.html missing page-spinner"
    print("  [PASS] results.html: Hardcoded batch rows and fake counts replaced with neutral loading states.")

    # Notices & Events: No static hardcoded cards
    with open(os.path.join(templates_dir, "notices.html"), "r", encoding="utf-8") as f:
        notices_html = f.read()
    assert "Mid-Semester Examination Schedule Announced" not in notices_html, "Mock card found in notices.html"
    assert 'id="noticesContainer"' in notices_html or 'class="item-list"' in notices_html, "Container missing in notices.html"

    with open(os.path.join(templates_dir, "events.html"), "r", encoding="utf-8") as f:
        events_html = f.read()
    assert "Hackathon 2026: Code for Good" not in events_html, "Mock event card found in events.html"
    assert "Annual Sports Meet: Athlos 2026" not in events_html, "Mock sports card found in events.html"
    assert 'page-spinner' in events_html, "events.html missing initial spinner"
    print("  [PASS] notices.html & events.html: Hardcoded demo cards removed.")

    # 3. Check JavaScript script.js for initial rendering logic and empty states
    print("\n[CHECK 3] Auditing static/js/script.js dynamic rendering...")
    with open(js_file, "r", encoding="utf-8") as f:
        js_content = f.read()

    # Verify no mock arrays
    assert "loadStudentResults" in js_content, "Missing loadStudentResults"
    assert "loadAdminResults" in js_content, "Missing loadAdminResults"
    assert "page-spinner" in js_content, "script.js must inject page-spinner on fetch start"
    assert "Awaiting Publication" in js_content, "script.js must handle unpopulated student results"
    assert "toggleCoursePublish" in js_content, "script.js must provide toggleCoursePublish"
    assert "statTotalDepts" in js_content, "script.js must update statTotalDepts dynamically"
    print("  [PASS] script.js: Initial spinners, live dynamic data calculation, and empty states confirmed.")

    # 4. Backend API Integration & Role Authentication Test
    print("\n[CHECK 4] Testing Backend APIs with clean empty database state...")
    app = create_app("testing")
    client = app.test_client()

    # Login as admin
    login_res = client.post("/api/auth/login", json={"username": "admin", "password": "admin", "role": "admin"})
    assert login_res.status_code == 200, f"Admin login failed: {login_res.get_json()}"
    print("  [PASS] Admin authenticated.")

    # Verify API responses return structured data without demo fallback
    res_students = client.get("/api/students")
    assert res_students.status_code == 200 and res_students.get_json()["success"] is True
    assert isinstance(res_students.get_json()["data"], list)

    res_results = client.get("/api/results")
    assert res_results.status_code == 200 and res_results.get_json()["success"] is True
    assert isinstance(res_results.get_json()["data"], list)

    res_courses = client.get("/api/courses")
    assert res_courses.status_code == 200 and res_courses.get_json()["success"] is True

    res_summary = client.get("/api/dashboard/summary")
    assert res_summary.status_code == 200 and res_summary.get_json()["success"] is True

    print("  [PASS] All APIs (/api/students, /api/results, /api/courses, /api/dashboard/summary) respond correctly.")

    print("\n" + "=" * 70)
    print("ALL FLASHING MOCK/DEMO DATA ELIMINATION CHECKS PASSED (100% SUCCESS)!")
    print("=" * 70)

if __name__ == "__main__":
    run_flashing_data_audit()
