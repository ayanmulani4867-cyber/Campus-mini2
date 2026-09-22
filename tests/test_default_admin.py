import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app import create_app
from extensions import db
from models import User
from seed import ensure_default_admin, run_seed


def test_default_admin():
    print("\n" + "=" * 70)
    print("TESTING DEFAULT ADMINISTRATOR INITIALIZATION & LOGIN")
    print("=" * 70)

    app = create_app()
    with app.app_context():
        # 1. Run ensure_default_admin
        print("\n--- 1. Testing ensure_default_admin() ---")
        admin = ensure_default_admin()
        assert admin is not None, "Admin user must be returned"
        assert admin.role == "admin", f"Role must be admin, got {admin.role}"
        assert admin.is_active is True, "Admin must be active"
        print(f"[PASS] Default admin created/verified: email={admin.email}, role={admin.role}")

        # 2. Test Idempotency (multiple runs)
        print("\n--- 2. Testing Idempotency (multiple runs) ---")
        admin2 = ensure_default_admin()
        assert admin2.id == admin.id, "Must not create a new admin row"
        admin_count = User.query.filter(
            db.or_(User.email.ilike("admin@campus.edu"), User.email.ilike("admin"))
        ).count()
        assert admin_count == 1, f"Expected exactly 1 admin user, found {admin_count}"
        print(f"[PASS] Idempotency confirmed: exactly 1 admin user exists across multiple invocations.")

        # 3. Test Password Security (never stored as plain text)
        print("\n--- 3. Testing Secure Password Hashing ---")
        assert admin.password_hash != "admin", "Password must NEVER be stored as plain text!"
        assert admin.password_hash.startswith("scrypt:") or admin.password_hash.startswith("pbkdf2:"), \
            f"Password must be securely hashed, got hash prefix: {admin.password_hash[:15]}"
        assert admin.check_password("admin") is True, "admin.check_password('admin') must return True"
        assert admin.check_password("wrong") is False, "admin.check_password('wrong') must return False"
        print(f"[PASS] Password securely hashed with algorithm prefix: {admin.password_hash.split('$')[0]}")

        # 4. Run full seed and re-verify
        print("\n--- 4. Running full run_seed() and verifying admin remains intact ---")
        run_seed()
        admin_count_after_seed = User.query.filter(
            db.or_(User.email.ilike("admin@campus.edu"), User.email.ilike("admin"))
        ).count()
        assert admin_count_after_seed == 1, f"Expected 1 admin after seed, got {admin_count_after_seed}"
        print("[PASS] Admin account preserved cleanly through run_seed().")

    client = app.test_client()

    # 5. Test Login Variations
    print("\n--- 5. Testing Login Scenarios via /api/auth/login ---")
    
    # 5a. Login with Username: admin, Password: admin
    res = client.post("/api/auth/login", json={"username": "admin", "password": "admin", "role": "admin"})
    assert res.status_code == 200, f"Login failed: {res.get_json()}"
    data = res.get_json()
    assert data["success"] is True
    assert data["data"]["role"] == "admin"
    print("[PASS] Login: username='admin', password='admin', role='admin'")

    # 5b. Login with Email: admin@campus.edu, Password: admin
    res = client.post("/api/auth/login", json={"email": "admin@campus.edu", "password": "admin", "role": "admin"})
    assert res.status_code == 200, f"Login failed: {res.get_json()}"
    print("[PASS] Login: email='admin@campus.edu', password='admin', role='admin'")

    # 5c. Login with Email: admin (as identifier), Password: admin
    res = client.post("/api/auth/login", json={"email": "admin", "password": "admin", "role": "admin"})
    assert res.status_code == 200, f"Login failed: {res.get_json()}"
    print("[PASS] Login: email='admin', password='admin', role='admin'")

    # 5d. Backwards compatibility: password='campus@123'
    res = client.post("/api/auth/login", json={"email": "admin@campus.edu", "password": "campus@123", "role": "admin"})
    assert res.status_code == 200, f"Login failed: {res.get_json()}"
    print("[PASS] Login: email='admin@campus.edu', password='campus@123' (legacy test compatibility)")

    # 5e. Invalid Password
    res = client.post("/api/auth/login", json={"username": "admin", "password": "wrong_password"})
    assert res.status_code == 401, f"Expected 401 for wrong password, got {res.status_code}"
    print("[PASS] Security: wrong password correctly rejected with 401.")

    # 5f. Role Mismatch
    res = client.post("/api/auth/login", json={"username": "admin", "password": "admin", "role": "student"})
    assert res.status_code == 403, f"Expected 403 for role mismatch, got {res.status_code}"
    print("[PASS] RBAC: role mismatch correctly rejected with 403.")

    print("\n" + "=" * 70)
    print("ALL DEFAULT ADMINISTRATOR TESTS PASSED (100% SUCCESS)!")
    print("=" * 70)


if __name__ == "__main__":
    test_default_admin()
