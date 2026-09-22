import io
import os
from pathlib import Path
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename
from flask import send_file

ALLOWED_EXTENSIONS = {"pdf", "ppt", "pptx"}
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB

MIME_TYPE_MAP = {
    "pdf": "application/pdf",
    "ppt": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}

# Magic byte signatures for secure content verification
MAGIC_SIGNATURES = {
    "pdf": [b"%PDF"],
    "ppt": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"],
    "pptx": [b"PK\x03\x04"],  # PPTX is an OpenXML ZIP archive
}


class StorageService:
    """PostgreSQL BYTEA file storage service.
    Validates uploaded files (extension, magic bytes, size <= 25MB)
    and prepares them for persistent database storage without local disk dependency.
    """

    ALLOWED_EXTENSIONS = ALLOWED_EXTENSIONS
    MAX_FILE_SIZE = MAX_FILE_SIZE

    def is_allowed_extension(self, filename: str) -> bool:
        if not filename or "." not in filename:
            return False
        ext = filename.rsplit(".", 1)[1].lower()
        return ext in ALLOWED_EXTENSIONS

    def get_extension(self, filename: str) -> str:
        if not filename or "." not in filename:
            return ""
        return filename.rsplit(".", 1)[1].lower()

    def get_mime_type(self, filename: str, fallback_mime: str = None) -> str:
        ext = self.get_extension(filename)
        return MIME_TYPE_MAP.get(ext, fallback_mime or "application/octet-stream")

    def validate_and_read(self, uploaded: FileStorage) -> dict:
        """Securely inspects an uploaded FileStorage object:
        1. Checks presence of file and filename
        2. Validates allowed extension (.pdf, .ppt, .pptx)
        3. Reads file bytes and checks maximum size (25MB)
        4. Validates file header / magic bytes against declared extension
        5. Returns sanitized metadata and raw bytes for PostgreSQL BYTEA storage.
        """
        if not uploaded or not uploaded.filename:
            raise ValueError("No file provided.")

        raw_name = uploaded.filename.strip()
        if not self.is_allowed_extension(raw_name):
            allowed_list = ", ".join(sorted(f".{e}" for e in ALLOWED_EXTENSIONS))
            raise ValueError(f"Invalid file extension. Only {allowed_list} files are permitted.")

        ext = self.get_extension(raw_name)

        # Read binary data
        uploaded.stream.seek(0)
        file_bytes = uploaded.read()
        file_size = len(file_bytes)

        if file_size == 0:
            raise ValueError("Uploaded file is empty.")

        if file_size > MAX_FILE_SIZE:
            max_mb = MAX_FILE_SIZE // (1024 * 1024)
            raise ValueError(f"File size ({file_size / (1024 * 1024):.1f} MB) exceeds maximum allowed limit of {max_mb} MB.")

        # Magic bytes verification (first 8 bytes)
        expected_magics = MAGIC_SIGNATURES.get(ext, [])
        if expected_magics:
            matches_magic = any(file_bytes.startswith(sig) for sig in expected_magics)
            if not matches_magic:
                raise ValueError(f"File content does not match the declared .{ext} format.")

        safe_name = secure_filename(raw_name) or f"uploaded_document.{ext}"
        mime_type = MIME_TYPE_MAP.get(ext, uploaded.mimetype or "application/octet-stream")

        return {
            "file_bytes": file_bytes,
            "file_name": safe_name,
            "file_size_bytes": file_size,
            "mime_type": mime_type,
            "extension": ext,
        }

    def create_download_response(self, file_bytes: bytes, filename: str, mime_type: str = None):
        """Streams binary data stored in PostgreSQL BYTEA as a downloadable attachment."""
        if not file_bytes:
            raise ValueError("No file data available for download.")

        ext = self.get_extension(filename)
        effective_mime = mime_type or MIME_TYPE_MAP.get(ext, "application/octet-stream")

        return send_file(
            io.BytesIO(file_bytes),
            mimetype=effective_mime,
            as_attachment=True,
            download_name=filename or f"download.{ext or 'bin'}",
        )


# Singleton storage service instance
storage_service = StorageService()
