"""
Non-destructive Firebase connectivity and project credentials verification utility.
Performs read-only validation of:
1. Firebase Realtime Database project URL and DNS availability
2. Service Account Key validity and project_id matching ('campus-mini2')
3. Firebase Admin SDK read-only authentication (RTDB shallow read & Auth list_users)
4. Absence of destructive write attempts
"""

import sys
import os
import json
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import requests

EXPECTED_PROJECT_ID = "campus-mini2"
TARGET_RTDB_URL = "https://campus-mini2-default-rtdb.firebaseio.com/"


def test_public_endpoint_availability():
    """Tests DNS resolution and security rule enforcement via shallow HTTP request."""
    print("=" * 70)
    print("STEP 1: Firebase RTDB Endpoint Reachability & Security Check")
    print("=" * 70)
    test_url = f"{TARGET_RTDB_URL.rstrip('/')}/.json?shallow=true"
    print(f"Target URL: {test_url}")
    try:
        resp = requests.get(test_url, timeout=10)
        print(f"HTTP Status Code: {resp.status_code}")
        if resp.status_code == 401:
            print("[PASS] Endpoint is ACTIVE and protected by Firebase Security Rules (.read: false).")
            print("       Public unauthenticated access is properly denied.")
            return True, "Active (Protected by Security Rules)"
        elif resp.status_code == 200:
            print("[WARN] Endpoint responded with 200 OK without authentication.")
            return True, "Active (Publicly Readable)"
        else:
            print(f"[INFO] Endpoint responded with status: {resp.status_code} - {resp.text[:200]}")
            return True, f"HTTP {resp.status_code}"
    except Exception as e:
        print(f"[FAIL] Failed to reach Firebase RTDB endpoint: {e}")
        return False, str(e)


def inspect_credentials():
    """Inspects available Firebase credentials without writing anything."""
    print("\n" + "=" * 70)
    print("STEP 2: Firebase Credentials & Project Identity Inspection")
    print("=" * 70)

    cred_data = None
    cred_source = None

    # Check env var FIREBASE_SERVICE_ACCOUNT_KEY
    env_key = os.environ.get("FIREBASE_SERVICE_ACCOUNT_KEY")
    if env_key:
        try:
            cred_data = json.loads(env_key)
            cred_source = "Environment Variable (FIREBASE_SERVICE_ACCOUNT_KEY)"
        except Exception as e:
            print(f"[FAIL] FIREBASE_SERVICE_ACCOUNT_KEY env var contains invalid JSON: {e}")

    # Check file path in FIREBASE_CREDENTIALS_PATH
    if not cred_data:
        env_path = os.environ.get("FIREBASE_CREDENTIALS_PATH")
        if env_path and Path(env_path).is_file():
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    cred_data = json.load(f)
                cred_source = f"File from FIREBASE_CREDENTIALS_PATH: {env_path}"
            except Exception as e:
                print(f"[FAIL] Failed reading credentials from {env_path}: {e}")

    # Check local serviceAccountKey.json
    if not cred_data:
        local_key = BASE_DIR / "serviceAccountKey.json"
        if local_key.is_file():
            try:
                with open(local_key, "r", encoding="utf-8") as f:
                    cred_data = json.load(f)
                cred_source = f"Local file: {local_key}"
            except Exception as e:
                print(f"[FAIL] Failed reading local serviceAccountKey.json: {e}")

    if not cred_data:
        print("[STATUS] Live credentials not yet supplied in workspace.")
        print("         To connect with full admin privileges, place your Firebase")
        print("         Service Account JSON in:")
        print(f"           1. File: {BASE_DIR / 'serviceAccountKey.json'} (excluded from git), OR")
        print("           2. Env var: FIREBASE_SERVICE_ACCOUNT_KEY (single-line JSON)")
        return None, None

    print(f"Credentials Source: {cred_source}")
    project_id = cred_data.get("project_id")
    client_email = cred_data.get("client_email")
    private_key_id = cred_data.get("private_key_id")

    # Strict privacy safeguard: Never print or expose the private_key
    print(f"  • Project ID      : {project_id}")
    print(f"  • Client Email    : {client_email}")
    print(f"  • Private Key ID  : {private_key_id[:8] if private_key_id else 'None'}... (truncated)")
    print(f"  • Private Key     : [SECURED / NEVER PRINTED / ZERO EXPOSURE]")

    # Verify Git ignore exclusion
    local_key = BASE_DIR / "serviceAccountKey.json"
    if local_key.is_file():
        import subprocess
        try:
            res = subprocess.run(
                ["git", "check-ignore", "-v", "serviceAccountKey.json"],
                cwd=str(BASE_DIR),
                capture_output=True,
                text=True
            )
            if res.returncode == 0:
                print(f"  • Git Exclusion   : [PASS] Excluded from Git commits ({res.stdout.strip()})")
            else:
                print(f"  • Git Exclusion   : [WARN] Not matched by .gitignore!")
        except Exception:
            pass

    if project_id != EXPECTED_PROJECT_ID:
        print(f"[FAIL] Credential project_id '{project_id}' DOES NOT MATCH expected '{EXPECTED_PROJECT_ID}'!")
        return None, None
    else:
        print(f"[PASS] Project ID verified: matches target '{EXPECTED_PROJECT_ID}'.")

    return cred_data, cred_source


def test_admin_sdk_non_destructive(cred_data):
    """Executes non-destructive read-only calls using Firebase Admin SDK."""
    print("\n" + "=" * 70)
    print("STEP 3: Firebase Admin SDK Non-Destructive Authentication")
    print("=" * 70)

    if not cred_data:
        print("[SKIPPED] Skipped Admin SDK live connection (credentials not provided).")
        return False

    try:
        import firebase_admin
        from firebase_admin import credentials, db, auth

        # Create isolated app for testing to avoid collisions
        app_name = "test_connectivity_app"
        try:
            test_app = firebase_admin.get_app(app_name)
            firebase_admin.delete_app(test_app)
        except ValueError:
            pass

        cred = credentials.Certificate(cred_data)
        test_app = firebase_admin.initialize_app(
            cred,
            {"databaseURL": TARGET_RTDB_URL},
            name=app_name
        )

        # 1. Non-destructive RTDB read
        print("Performing non-destructive RTDB read (0 writes)...", flush=True)
        root_ref = db.reference("/", app=test_app)
        data = root_ref.get()
        if data is None:
            print("[PASS] RTDB Read Successful! Target Realtime Database is connected, clean, and empty (ready for migration).", flush=True)
        elif isinstance(data, dict):
            keys_found = list(data.keys())
            print(f"[PASS] RTDB Read Successful! Existing collections found: {len(keys_found)}", flush=True)
            print(f"       Collections: {', '.join(keys_found[:8])}...", flush=True)
        else:
            print(f"[PASS] RTDB Read Successful! Data type: {type(data)}", flush=True)

        # 2. Non-destructive Auth list users
        print("Performing non-destructive Firebase Auth read (0 writes)...", flush=True)
        users_page = auth.list_users(max_results=10, app=test_app)
        auth_users = len(users_page.users)
        print(f"[PASS] Firebase Auth Read Successful! Verified connection to Firebase Auth (Existing users: {auth_users}).", flush=True)

        # Cleanup test app
        firebase_admin.delete_app(test_app)
        return True
    except Exception as e:
        print(f"[FAIL] Firebase Admin SDK test failed: {e}")
        return False


def main():
    print("CAMPUS CONNECT ERP - FIREBASE CONNECTIVITY VERIFICATION")
    print("Target RTDB: " + TARGET_RTDB_URL)
    print("Mode: STRICT READ-ONLY (0 writes, 0 mutations)")
    print()

    endpoint_ok, msg = test_public_endpoint_availability()
    cred_data, cred_source = inspect_credentials()
    sdk_ok = test_admin_sdk_non_destructive(cred_data)

    print("\n" + "=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    print(f"  • RTDB Endpoint Reached : {'YES' if endpoint_ok else 'NO'} ({msg})")
    print(f"  • Credentials Provided  : {'YES' if cred_data else 'PENDING USER ACTION'}")
    print(f"  • Admin SDK Verified    : {'YES (Ready)' if sdk_ok else 'PENDING CREDENTIALS'}")
    print("  • Database Writes       : 0 (Strictly non-destructive)")
    print("=" * 70)


if __name__ == "__main__":
    main()
