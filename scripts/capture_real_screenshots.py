import os
import sys
import time
import threading

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from playwright.sync_api import sync_playwright

SCREENSHOT_DIR = os.path.join(REPO_ROOT, "docs", "screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
BASE_URL = "http://127.0.0.1:5005"

def run_flask():
    from app import create_app
    app = create_app()
    app.run(host="127.0.0.1", port=5005, debug=False, use_reloader=False)

def wait_for_server():
    import urllib.request
    for _ in range(30):
        try:
            resp = urllib.request.urlopen(f"{BASE_URL}/login.html", timeout=1)
            if resp.status == 200:
                print("Flask server ready!")
                return True
        except Exception:
            time.sleep(0.5)
    return False

def capture_all():
    print(f"Target directory: {SCREENSHOT_DIR}")
    
    # Start flask in thread
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
    
    if not wait_for_server():
        print("Failed to start Flask server.")
        sys.exit(1)
        
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=EDGE_PATH,
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=1.5
        )
        page = context.new_page()

        # 1. Login Page
        print("Capturing 01_login_portal.png...")
        page.goto(f"{BASE_URL}/login.html")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "01_login_portal.png"))

        # 2. Login as Admin
        print("Logging in as Admin...")
        admin_tab = page.locator('.role-tab[data-role="admin"]')
        if admin_tab.count() > 0:
            admin_tab.click()
            time.sleep(0.3)
        page.fill("#loginId", "admin@campus.edu")
        page.fill("#loginPassword", "admin")
        page.click('button[type="submit"]')
        page.wait_for_url("**/dashboard.html", timeout=15000)
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        print("Capturing 02_admin_dashboard.png...")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "02_admin_dashboard.png"))

        # 3. Admin User Directory
        print("Navigating to users.html...")
        page.goto(f"{BASE_URL}/users.html")
        page.wait_for_load_state("networkidle")
        try:
            page.wait_for_selector("#usersTableBody tr, table tbody tr", timeout=10000)
        except Exception as e:
            print("Table selector wait:", e)
        time.sleep(2)
        print("Capturing 03_user_directory.png...")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "03_user_directory.png"))

        # 4. Student Attendance (Login as Student)
        print("Logging in as Student...")
        page.goto(f"{BASE_URL}/login.html")
        page.wait_for_load_state("networkidle")
        student_tab = page.locator('.role-tab[data-role="student"]')
        if student_tab.count() > 0:
            student_tab.click()
            time.sleep(0.3)
        page.fill("#loginId", "student.test@sitcoe.ac.in")
        page.fill("#loginPassword", "student123")
        page.click('button[type="submit"]')
        page.wait_for_url("**/dashboard.html", timeout=15000)
        page.wait_for_load_state("networkidle")
        time.sleep(1)

        print("Navigating to attendance.html...")
        page.goto(f"{BASE_URL}/attendance.html")
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        print("Capturing 04_student_attendance.png...")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "04_student_attendance.png"))

        # 5. Student Results
        print("Navigating to results.html as Student...")
        page.goto(f"{BASE_URL}/results.html")
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        print("Capturing 05_student_results.png...")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "05_student_results.png"))

        # 6. Faculty Marks Entry & Result Control
        print("Logging in as Faculty...")
        page.goto(f"{BASE_URL}/login.html")
        page.wait_for_load_state("networkidle")
        fac_tab = page.locator('.role-tab[data-role="faculty"]')
        if fac_tab.count() > 0:
            fac_tab.click()
            time.sleep(0.3)
        page.fill("#loginId", "prof.test@sitcoe.ac.in")
        page.fill("#loginPassword", "faculty123")
        page.click('button[type="submit"]')
        page.wait_for_url("**/dashboard.html", timeout=15000)
        page.wait_for_load_state("networkidle")
        time.sleep(1)

        print("Navigating to results.html as Faculty...")
        page.goto(f"{BASE_URL}/results.html")
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        print("Capturing 06_faculty_results_management.png...")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "06_faculty_results_management.png"))

        # 7. Notices
        print("Navigating to notices.html...")
        page.goto(f"{BASE_URL}/notices.html")
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        print("Capturing 07_notices_bulletin.png...")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "07_notices_bulletin.png"))

        # 8. Assignments
        print("Navigating to assignments.html...")
        page.goto(f"{BASE_URL}/assignments.html")
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        print("Capturing 08_assignments_management.png...")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "08_assignments_management.png"))

        browser.close()
        print("All screenshots successfully captured!")

if __name__ == "__main__":
    capture_all()
