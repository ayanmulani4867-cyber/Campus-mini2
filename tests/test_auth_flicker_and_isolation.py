"""
Auth Isolation and Flicker Verification Test Suite
==================================================
Tests:
TEST 1: Login Student A -> refresh 10 times -> Student A verified every time.
TEST 2: Logout -> Login Student B -> refresh 10 times -> Student B verified every time.
TEST 3: Student A logout -> Student B login -> verify no Student A data appears anywhere.
TEST 4: Two concurrent isolated client sessions (Client A = Student A, Client B = Student B)
        refreshed repeatedly -> verify data never crosses.
TEST 5: Faculty login -> refresh repeatedly -> verify faculty data remains correct.
TEST 6: Admin login -> refresh repeatedly -> verify admin data remains correct.
TEST 7: Unauthenticated access to protected pages -> 302 Redirect to /login.html.
TEST 8: Security & Cache-Control headers -> ensure no-store on sensitive endpoints, cacheable static.
"""

import os
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Use DATABASE_URL from environment or fallback to test configuration
if not os.environ.get("DATABASE_URL"):
    test_db = os.environ.get("TEST_DATABASE_URL")
    if test_db:
        os.environ["DATABASE_URL"] = test_db

import json
from app import create_app
from extensions import db
from models import User

def login(client, identifier, password, role=None):
    payload = {"email": identifier, "password": password}
    if role:
        payload["role"] = role
    res = client.post("/api/auth/login", data=json.dumps(payload), content_type="application/json")
    assert res.status_code == 200, f"Login failed: {res.data}"
    data = res.get_json()
    token = data.get("sessionToken")
    return token, data.get("data")

def logout(client, token=None):
    headers = {"X-Session-Token": token} if token else {}
    res = client.post("/api/auth/logout", headers=headers)
    assert res.status_code == 200, f"Logout failed: {res.data}"
    return res

def run_tests():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SERVER_NAME"] = "localhost"

    with app.app_context():
        # TEST 1: Login Student A (Priya Patel) -> refresh 10 times
        print("\n[RUNNING] TEST 1: Login as Student A (Priya Patel) -> refresh 10 times ...")
        client = app.test_client()
        token, user_a = login(client, "priya.patel@campus.edu", "campus@123", "student")
        stu_name = user_a["name"]
        assert stu_name == "Priya Patel"
        for i in range(10):
            res = client.get("/dashboard.html", headers={"X-Session-Token": token})
            assert res.status_code == 200, f"Refresh {i+1} failed"
            html = res.data.decode("utf-8")
            assert stu_name in html, f"Refresh {i+1}: Student A name not in HTML"
            # User B (John Snow / Aman Verma) must NEVER appear
            assert "John Snow" not in html, f"Refresh {i+1}: Demo/other user John Snow leaked in HTML"
            assert "Aman Verma" not in html, f"Refresh {i+1}: Student B leaked in HTML"
        print("  [PASS] Student A data rendered consistently on all 10 refreshes, no other user data")

        # TEST 2: Logout -> login Student B (Aman Verma) -> refresh 10 times
        print("\n[RUNNING] TEST 2: Logout -> login Student B (Aman Verma) -> refresh 10 times ...")
        logout(client, token)
        token_b, user_b = login(client, "aman.verma@campus.edu", "campus@123", "student")
        stu_b_name = user_b["name"]
        assert stu_b_name == "Aman Verma"
        for i in range(10):
            res = client.get("/dashboard.html", headers={"X-Session-Token": token_b})
            assert res.status_code == 200, f"Refresh {i+1} failed"
            html = res.data.decode("utf-8")
            assert stu_b_name in html, f"Refresh {i+1}: Student B name not in HTML"
            assert "Priya Patel" not in html, f"Refresh {i+1}: Student A name leaked to Student B"
            assert "John Snow" not in html
        print("  [PASS] Student B data rendered consistently on all 10 refreshes, no Student A data")

        # TEST 3: Student A logout -> Student B login isolation
        print("\n[RUNNING] TEST 3: Student A logout -> Student B login cross-contamination check ...")
        res_me = client.get("/api/auth/me", headers={"X-Session-Token": token_b})
        assert res_me.status_code == 200
        assert res_me.get_json()["data"]["name"] == user_b["name"]
        assert res_me.get_json()["data"]["email"] == "aman.verma@campus.edu"

        res_prof = client.get("/profile.html", headers={"X-Session-Token": token_b})
        assert res_prof.status_code == 200
        html_prof = res_prof.data.decode("utf-8")
        assert user_b["name"] in html_prof
        assert user_a["name"] not in html_prof
        assert "priya.patel@campus.edu" not in html_prof
        assert "John Snow" not in html_prof

        res_dash = client.get("/dashboard.html", headers={"X-Session-Token": token_b})
        html_dash = res_dash.data.decode("utf-8")
        assert user_b["name"] in html_dash
        assert user_a["name"] not in html_dash
        assert "John Snow" not in html_dash
        print("  [PASS] No trace of Student A in Student B's session or pages")

        # TEST 4: Two concurrent browser sessions
        print("\n[RUNNING] TEST 4: Concurrent isolated browser sessions (Client A & Client B) ...")
        client_a = app.test_client()
        client_b = app.test_client()
        token_a, user_a = login(client_a, "priya.patel@campus.edu", "campus@123", "student")
        token_b, user_b = login(client_b, "aman.verma@campus.edu", "campus@123", "student")

        for _ in range(10):
            res_a = client_a.get("/dashboard.html", headers={"X-Session-Token": token_a})
            html_a = res_a.data.decode("utf-8")
            assert user_a["name"] in html_a
            assert user_b["name"] not in html_a
            assert "John Snow" not in html_a

            res_b = client_b.get("/dashboard.html", headers={"X-Session-Token": token_b})
            html_b = res_b.data.decode("utf-8")
            assert user_b["name"] in html_b
            assert user_a["name"] not in html_b
            assert "John Snow" not in html_b
        print("  [PASS] Concurrent sessions completely isolated over 10 cross-refreshes")

        # TEST 5: Faculty login and refresh
        print("\n[RUNNING] TEST 5: Faculty login and repeated refresh ...")
        client_fac = app.test_client()
        token_fac, user_fac = login(client_fac, "anita.sen@campus.edu", "campus@123", "faculty")
        fac_name = user_fac["name"]

        for _ in range(5):
            res = client_fac.get("/dashboard.html", headers={"X-Session-Token": token_fac})
            html = res.data.decode("utf-8")
            assert fac_name in html
            assert "Faculty" in html
            assert "John Snow" not in html

            res_att = client_fac.get("/attendance.html", headers={"X-Session-Token": token_fac})
            html_att = res_att.data.decode("utf-8")
            assert fac_name in html_att
            assert "facultyRollCallCard" in html_att
            assert "display: block;" in html_att
            assert "John Snow" not in html_att
        print("  [PASS] Faculty dashboard and attendance controls verified cleanly")

        # TEST 6: Admin login and refresh
        print("\n[RUNNING] TEST 6: Admin login and repeated refresh ...")
        client_adm = app.test_client()
        token_adm, user_adm = login(client_adm, "admin@campus.edu", "campus@123", "admin")
        adm_name = user_adm["name"]

        for _ in range(5):
            res = client_adm.get("/dashboard.html", headers={"X-Session-Token": token_adm})
            html = res.data.decode("utf-8")
            assert adm_name in html
            assert "Administrator" in html
            assert "John Snow" not in html

            res_users = client_adm.get("/users.html", headers={"X-Session-Token": token_adm})
            assert res_users.status_code == 200
            html_users = res_users.data.decode("utf-8")
            assert adm_name in html_users
            assert "John Snow" not in html_users
        print("  [PASS] Admin dashboard and user directory verified cleanly")

        # TEST 7: Unauthenticated protected pages redirect
        print("\n[RUNNING] TEST 7: Unauthenticated protected pages gating ...")
        client_unauth = app.test_client()
        for page in ["/dashboard.html", "/profile.html", "/results.html", "/attendance.html", "/courses.html", "/users.html"]:
            res = client_unauth.get(page)
            assert res.status_code in (302, 401), f"{page} did not require authentication (got {res.status_code})"
            if res.status_code == 302:
                assert "/login.html" in res.headers.get("Location", "")
        print("  [PASS] Unauthenticated access blocked and redirected to /login.html")

        # TEST 8: Cache-Control headers
        print("\n[RUNNING] TEST 8: Cache-Control no-store headers validation ...")
        res_login = client_unauth.get("/login.html")
        assert "no-store" in res_login.headers.get("Cache-Control", "")
        res_health = client_unauth.get("/api/health")
        assert "no-store" in res_health.headers.get("Cache-Control", "")

        res_css = client_unauth.get("/css/style.css")
        cc_css = res_css.headers.get("Cache-Control", "")
        assert "no-store" not in cc_css, f"Static asset unexpectedly got no-store: {cc_css}"
        print("  [PASS] Sensitive endpoints have no-store; static assets remain cacheable")

        print("\n" + "=" * 70)
        print("ALL 8 VERIFICATION TESTS PASSED SUCCESSFULLY!")
        print("=" * 70)

if __name__ == "__main__":
    run_tests()
