import io
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import app
from extensions import db
from models import (
    User, Student, Faculty, FacultyAssignment, Course, Department,
    StudyMaterial, Assignment, AssignmentSubmission
)


def run_storage_tests():
    print("=" * 80)
    print("CAMPUS CONNECT — POSTGRESQL BYTEA FILE STORAGE VERIFICATION SUITE")
    print("=" * 80)

    client = app.test_client()

    with app.app_context():
        # Clean up any previous test artifacts
        old_mats = StudyMaterial.query.filter(StudyMaterial.title.like("TEST_%")).all()
        for m in old_mats:
            db.session.delete(m)
        old_assigns = Assignment.query.filter(Assignment.title.like("TEST_%")).all()
        for a in old_assigns:
            db.session.delete(a)
        db.session.commit()

        # ---------------------------------------------------------------------
        # 1. Authenticate Users (Faculty, Student, Admin)
        # ---------------------------------------------------------------------
        print("\n--- 1. Authenticating Roles ---")
        fac_login = client.post("/api/auth/login", json={"email": "anita.sen@campus.edu", "password": "campus@123", "role": "faculty"})
        assert fac_login.status_code == 200, f"Faculty login failed: {fac_login.get_json()}"
        fac_token = fac_login.get_json()["sessionToken"]
        fac_headers = {"X-Session-Token": fac_token}
        print("✓ Faculty (anita.sen@campus.edu) authenticated.")

        stu_login = client.post("/api/auth/login", json={"email": "rahul@campus.edu", "password": "campus@123", "role": "student"})
        assert stu_login.status_code == 200, f"Student login failed: {stu_login.get_json()}"
        stu_token = stu_login.get_json()["sessionToken"]
        stu_headers = {"X-Session-Token": stu_token}
        print("✓ Student (rahul@campus.edu) authenticated.")

        admin_login = client.post("/api/auth/login", json={"email": "admin@campus.edu", "password": "campus@123", "role": "admin"})
        assert admin_login.status_code == 200, f"Admin login failed: {admin_login.get_json()}"
        admin_token = admin_login.get_json()["sessionToken"]
        admin_headers = {"X-Session-Token": admin_token}
        print("✓ Admin (admin@campus.edu) authenticated.")

        # Ensure course CS601 exists
        course = Course.query.filter_by(code="CS601").first()
        assert course is not None, "Course CS601 must exist"

        # ---------------------------------------------------------------------
        # 2. Faculty Uploads PDF, PPT, and PPTX to PostgreSQL BYTEA
        # ---------------------------------------------------------------------
        print("\n--- 2. Faculty Uploading PDF, PPT, PPTX Files ---")

        # Realistic valid binary file contents with proper magic headers
        pdf_bytes = (
            b"%PDF-1.4\n"
            b"1 0 obj << /Title (Database Systems Chapter 1) >> endobj\n"
            b"trailer << /Root 1 0 R >>\n"
            b"%%EOF\n"
        )
        ppt_bytes = (
            b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # OLE Compound Document signature
            b"\x00" * 504 + b"MOCK_PPT_SLIDES_STREAM_DATA"
        )
        pptx_bytes = (
            b"PK\x03\x04"  # ZIP archive signature (used by .pptx OpenXML)
            b"\x14\x00\x06\x00\x08\x00" + b"\x00" * 20 + b"[Content_Types].xml" + b"MOCK_PPTX_PRESENTATION"
        )

        upload_specs = [
            ("TEST_DBMS_Lecture_Notes_PDF", "lecture_notes_unit1.pdf", pdf_bytes, "application/pdf"),
            ("TEST_DBMS_Slides_PPT", "lecture_slides_unit2.ppt", ppt_bytes, "application/vnd.ms-powerpoint"),
            ("TEST_DBMS_Advanced_PPTX", "lecture_deck_unit3.pptx", pptx_bytes, "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
        ]

        uploaded_mat_ids = {}

        for title, filename, raw_bytes, expected_mime in upload_specs:
            data = {
                "title": title,
                "category": "Notes",
                "courseCode": "CS601",
                "division": "A",
                "file": (io.BytesIO(raw_bytes), filename),
            }
            res = client.post("/api/materials", data=data, content_type="multipart/form-data", headers=fac_headers)
            assert res.status_code == 201, f"Failed to upload {filename}: {res.get_json()}"
            res_json = res.get_json()["data"]
            mat_id = res_json["id"]
            uploaded_mat_ids[filename] = mat_id

            # Verify response schema: NO filesystem path exposed!
            assert "filePath" not in res_json, "Security Violation: filePath must not be exposed in JSON!"
            assert "file_path" not in res_json, "Security Violation: file_path must not be exposed in JSON!"
            assert res_json["fileName"] == filename, f"Expected fileName={filename}, got {res_json.get('fileName')}"
            assert res_json["downloadUrl"] == f"/api/materials/{mat_id}/download"

            # Direct Database Inspection: verify BYTEA binary persistence in PostgreSQL!
            mat_db = StudyMaterial.query.get(mat_id)
            assert mat_db is not None, f"StudyMaterial row {mat_id} not found in database!"
            assert mat_db.file_data == raw_bytes, f"BYTEA data mismatch for {filename}!"
            assert mat_db.file_size_bytes == len(raw_bytes), "File size in DB does not match raw bytes length!"
            assert mat_db.file_name == filename
            assert mat_db.mime_type == expected_mime
            assert mat_db.file_path is None, "Ephemeral file_path must be None in production persistent mode!"
            assert mat_db.uploaded_by_id == User.query.filter_by(email="anita.sen@campus.edu").first().id
            assert mat_db.course_id == course.id

            print(f"✓ Uploaded {filename} -> DB ID={mat_id}, BYTEA size={len(mat_db.file_data)} bytes, MIME={mat_db.mime_type}")

        # ---------------------------------------------------------------------
        # 3. Student Lists Materials and Downloads PDF, PPT, PPTX
        # ---------------------------------------------------------------------
        print("\n--- 3. Student Listing Materials & Downloading from PostgreSQL BYTEA ---")
        list_res = client.get("/api/materials", headers=stu_headers)
        assert list_res.status_code == 200, f"List materials failed: {list_res.get_json()}"
        materials_list = list_res.get_json()["data"]
        item_ids = [m["id"] for m in materials_list]

        for filename, mat_id in uploaded_mat_ids.items():
            assert mat_id in item_ids, f"Student should see uploaded material ID={mat_id}"

        print(f"✓ Student successfully listed {len(materials_list)} study materials.")

        # Download and verify bit-for-bit parity
        for title, filename, original_bytes, expected_mime in upload_specs:
            mat_id = uploaded_mat_ids[filename]
            dl_res = client.get(f"/api/materials/{mat_id}/download", headers=stu_headers)
            assert dl_res.status_code == 200, f"Failed to download {filename}: {dl_res.status_code}"
            assert dl_res.data == original_bytes, f"Downloaded content does not match original bytes for {filename}!"
            assert dl_res.headers.get("Content-Type") == expected_mime
            assert filename in dl_res.headers.get("Content-Disposition", "")
            print(f"✓ Downloaded {filename} ({len(dl_res.data)} bytes) directly from PostgreSQL BYTEA — 100% BIT PARITY!")

        # ---------------------------------------------------------------------
        # 4. Assignment Submission with File, Faculty Access & Grading
        # ---------------------------------------------------------------------
        print("\n--- 4. Coursework Assignment File Submission & Grading ---")

        # Create an assignment
        from datetime import datetime, timezone, timedelta
        fac = Faculty.query.filter_by(faculty_code="FAC2018042").first()
        assign_payload = {
            "title": "TEST_Assignment_Normalization_Problem_Set",
            "description": "Submit normalization proofs and schema diagrams in PDF format.",
            "courseCode": "CS601",
            "dueDate": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "totalPoints": 100,
            "division": "A",
        }
        res_assign = client.post("/api/assignments", json=assign_payload, headers=fac_headers)
        assert res_assign.status_code == 201, f"Failed to create assignment: {res_assign.get_json()}"
        assign_id = res_assign.get_json()["data"]["id"]
        print(f"✓ Faculty created Assignment ID={assign_id}: '{assign_payload['title']}'")

        # Student submits assignment with PDF attachment
        submission_pdf_bytes = (
            b"%PDF-1.4\n"
            b"1 0 obj << /Title (Student Normalization Submission - Rahul STU2024001) >> endobj\n"
            b"trailer << /Root 1 0 R >>\n"
            b"%%EOF\n"
        )
        sub_form_data = {
            "submissionText": "Here is my completed normalization assignment including 3NF and BCNF decompositions.",
            "file": (io.BytesIO(submission_pdf_bytes), "rahul_assignment1_solution.pdf"),
        }
        sub_res = client.post(
            f"/api/assignments/{assign_id}/submit",
            data=sub_form_data,
            content_type="multipart/form-data",
            headers=stu_headers
        )
        assert sub_res.status_code in (200, 201), f"Submit assignment failed: {sub_res.get_json()}"
        sub_json = sub_res.get_json()["data"]
        sub_id = sub_json["id"]
        print(f"✓ Student submitted assignment with PDF attachment: Sub ID={sub_id}")

        # Verify DB persistence of student submission BYTEA
        sub_db = AssignmentSubmission.query.get(sub_id)
        assert sub_db is not None
        assert sub_db.file_data == submission_pdf_bytes, "Submission BYTEA data mismatch!"
        assert sub_db.file_name == "rahul_assignment1_solution.pdf"
        assert sub_db.mime_type == "application/pdf"
        assert sub_db.file_size_bytes == len(submission_pdf_bytes)
        print(f"✓ Verified AssignmentSubmission BYTEA stored in PostgreSQL ({len(sub_db.file_data)} bytes).")

        # Faculty reviews assignment and downloads student's PDF submission
        fac_get_assign = client.get(f"/api/assignments/{assign_id}", headers=fac_headers)
        assert fac_get_assign.status_code == 200
        submissions = fac_get_assign.get_json()["data"]["submissions"]
        assert len(submissions) == 1
        sub_summary = submissions[0]
        assert sub_summary["id"] == sub_id
        assert sub_summary["fileName"] == "rahul_assignment1_solution.pdf"
        assert sub_summary["downloadUrl"] == f"/api/assignments/{assign_id}/submissions/{sub_id}/download"
        assert "filePath" not in sub_summary, "Security: submission filePath must not be exposed!"

        # Faculty downloads student submission
        sub_dl_res = client.get(f"/api/assignments/{assign_id}/submissions/{sub_id}/download", headers=fac_headers)
        assert sub_dl_res.status_code == 200, f"Faculty download submission failed: {sub_dl_res.status_code}"
        assert sub_dl_res.data == submission_pdf_bytes, "Faculty downloaded submission bytes do not match submitted PDF!"
        print(f"✓ Faculty downloaded Student submission from PostgreSQL BYTEA — 100% BIT PARITY!")

        # Faculty grades the submission
        grade_res = client.post(f"/api/assignments/{assign_id}/grade", json={
            "studentId": "STU2024001",
            "grade": 96.5,
            "feedback": "Excellent schema normalization work and clear dependency diagram."
        }, headers=fac_headers)
        assert grade_res.status_code == 200, f"Grading failed: {grade_res.get_json()}"
        assert grade_res.get_json()["data"]["grade"] == 96.5
        assert grade_res.get_json()["data"]["status"] == "graded"
        print(f"✓ Faculty graded Student submission: 96.5/100, Status: 'graded'")

        # ---------------------------------------------------------------------
        # 5. Security & Validation Enforcement Tests
        # ---------------------------------------------------------------------
        print("\n--- 5. Security & Validation Checks ---")

        # Disallowed extension (.exe / .sh) rejected
        bad_file = (io.BytesIO(b"MALICIOUS_EXEC_DATA"), "exploit.exe")
        bad_res = client.post("/api/materials", data={"title": "Bad File", "file": bad_file}, content_type="multipart/form-data", headers=fac_headers)
        assert bad_res.status_code == 400, "Disallowed extension .exe must be rejected with 400!"
        print("✓ Disallowed extension (.exe) rejected with 400 ValidationError.")

        # File header mismatch (e.g. text file disguised as .pdf) rejected
        fake_pdf = (io.BytesIO(b"THIS_IS_PLAIN_TEXT_NOT_A_PDF"), "fake.pdf")
        fake_res = client.post("/api/materials", data={"title": "Fake PDF", "file": fake_pdf}, content_type="multipart/form-data", headers=fac_headers)
        assert fake_res.status_code == 400, "Header mismatch must be rejected with 400!"
        print("✓ Corrupted / forged file header rejected with 400 ValidationError.")

        # Size limit check: reject file > 25MB
        oversized_data = b"0" * (26 * 1024 * 1024)  # 26 MB
        oversized_file = (io.BytesIO(b"%PDF-1.4\n" + oversized_data), "huge_book.pdf")
        over_res = client.post("/api/materials", data={"title": "Oversized", "file": oversized_file}, content_type="multipart/form-data", headers=fac_headers)
        assert over_res.status_code == 400, "Oversized file > 25MB must be rejected with 400!"
        print("✓ Oversized file (>25 MB) rejected with 400 ValidationError.")

        # Access control: student cannot download another student's assignment submission
        stu2 = Student.query.filter_by(student_code="STU2024002").first()
        if stu2:
            # Login as STU2024002 (student Priya Sharma)
            stu2_login = client.post("/api/auth/login", json={"email": "priya.sharma@campus.edu", "password": "campus@123", "role": "student"})
            if stu2_login.status_code == 200:
                stu2_headers = {"X-Session-Token": stu2_login.get_json()["sessionToken"]}
                unauth_dl = client.get(f"/api/assignments/{assign_id}/submissions/{sub_id}/download", headers=stu2_headers)
                assert unauth_dl.status_code == 403, "Student must not be allowed to download another student's submission!"
                print("✓ Access control verified: unauthorized student blocked (403 Forbidden).")

        # Deletion from PostgreSQL
        del_mat_id = uploaded_mat_ids["lecture_notes_unit1.pdf"]
        del_res = client.delete(f"/api/materials/{del_mat_id}", headers=fac_headers)
        assert del_res.status_code == 200, f"Delete material failed: {del_res.get_json()}"
        assert StudyMaterial.query.get(del_mat_id) is None, "Material row must be deleted from database!"
        print(f"✓ Deletion verified: Material ID={del_mat_id} removed from PostgreSQL.")

        # Clean up remaining test records
        for title, filename, _, _ in upload_specs:
            mid = uploaded_mat_ids[filename]
            m = StudyMaterial.query.get(mid)
            if m:
                db.session.delete(m)
        a = Assignment.query.get(assign_id)
        if a:
            db.session.delete(a)
        db.session.commit()

    print("\n" + "=" * 80)
    print("ALL POSTGRESQL BYTEA FILE STORAGE TESTS PASSED SUCCESSFULLY (100% PASS)!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    run_storage_tests()
