from __future__ import annotations

import hashlib
import io
import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from pypdf import PdfReader


class UploadValidationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ValidatedUpload:
    safe_filename: str
    size_bytes: int
    sha256: str
    page_count: int


def sanitize_filename(filename: str) -> str:
    if "\x00" in filename or any(ord(char) < 32 for char in filename):
        raise UploadValidationError("invalid_filename", "The filename contains invalid characters.")
    normalized = filename.replace("\\", "/")
    basename = PurePosixPath(normalized).name
    if basename in {"", ".", ".."}:
        raise UploadValidationError("invalid_filename", "A valid PDF filename is required.")
    suffix = PurePosixPath(basename).suffix.lower()
    if suffix != ".pdf":
        raise UploadValidationError("extension_mismatch", "Only PDF files are supported.")
    safe = re.sub(r"[^A-Za-z0-9._ -]", "_", basename).strip(" .")
    safe = re.sub(r"\.{2,}", "_", safe)
    if not safe:
        safe = "document.pdf"
    if len(safe) > 120:
        safe = safe[:116].rstrip(" .") + ".pdf"
    if not safe.lower().endswith(".pdf"):
        safe += ".pdf"
    return safe


def validate_pdf_upload(
    data: bytes,
    filename: str,
    media_type: str | None,
    max_bytes: int,
) -> ValidatedUpload:
    safe_filename = sanitize_filename(filename)
    if not data:
        raise UploadValidationError("empty_file", "The uploaded file is empty.")
    if len(data) > max_bytes:
        raise UploadValidationError("file_too_large", "The PDF exceeds the upload size limit.")
    if (media_type or "").split(";", maxsplit=1)[0].strip().lower() != "application/pdf":
        raise UploadValidationError("unsupported_media_type", "Upload a PDF document.")
    if b"%PDF-" not in data[:1024]:
        raise UploadValidationError("invalid_signature", "The file does not have a PDF signature.")
    suspicious_tokens = (b"/JavaScript", b"/JS ", b"/Launch", b"/EmbeddedFile", b"/RichMedia")
    if any(token in data for token in suspicious_tokens):
        raise UploadValidationError(
            "active_content_detected", "This PDF contains active content and cannot be processed."
        )
    try:
        reader = PdfReader(io.BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise UploadValidationError(
                "password_protected", "Password-protected PDFs are not supported."
            )
        page_count = len(reader.pages)
        if page_count > 250:
            raise UploadValidationError("page_limit_exceeded", "The PDF exceeds the page limit.")
        if page_count < 1:
            raise UploadValidationError("malformed_pdf", "The PDF contains no pages.")
    except UploadValidationError:
        raise
    except Exception as exc:
        raise UploadValidationError("malformed_pdf", "The PDF could not be validated.") from exc
    return ValidatedUpload(
        safe_filename=safe_filename,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        page_count=page_count,
    )
