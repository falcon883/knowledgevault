"""
KnowledgeVault backend - KV-24: upload validation.

Everything that can be wrong with an uploaded file is checked here, before
anything is written to the database. Each problem raises an UploadError with
a status code, a short machine-readable `code`, and a plain-language
`detail` that the frontend can show to the user as is.

Every upload error comes back in the same shape (see main.py):

    {"detail": "<message for the user>", "code": "<machine_code>"}

| code                    | status | when                                        |
|-------------------------|--------|---------------------------------------------|
| no_file                 | 400    | request had no file                         |
| unsupported_type        | 415    | not a PDF or plain text file                |
| file_too_large          | 413    | bigger than MAX_UPLOAD_MB (default 10)      |
| empty_file              | 400    | zero bytes                                  |
| unreadable_pdf          | 422    | damaged, or not really a PDF                |
| password_protected_pdf  | 422    | PDF needs a password                        |
| unreadable_text         | 422    | not plain text (binary data)                |
| no_text                 | 422    | readable file, but no text in it            |
| duplicate_document      | 409    | same content as a document already stored   |
| processing_failed       | 500    | text was fine, saving or embedding failed   |

duplicate_document also carries `existing` ({id, filename, uploaded_at}) so
the frontend can point the user at the copy they already have.
"""

import hashlib
import io
import logging
import os

from dotenv import load_dotenv
from pypdf import PdfReader

load_dotenv()  # so MAX_UPLOAD_MB can live in .env, whatever imports this first

# pypdf logs a warning for every slightly malformed PDF. We turn real problems
# into clear errors ourselves, so keep its log quiet.
logging.getLogger("pypdf").setLevel(logging.ERROR)

MAX_UPLOAD_MB = float(os.getenv("MAX_UPLOAD_MB", "10"))
MAX_UPLOAD_BYTES = int(MAX_UPLOAD_MB * 1024 * 1024)

SUPPORTED_TYPES = {"application/pdf": "pdf", "text/plain": "text"}
EXTENSION_KINDS = {".pdf": "pdf", ".txt": "text"}
# Some browsers and tools send these when they don't know the file type, so
# for these we go by the file extension instead.
GENERIC_TYPES = {"", "application/octet-stream", "binary/octet-stream"}
KIND_CONTENT_TYPE = {"pdf": "application/pdf", "text": "text/plain"}

UNSUPPORTED_HINT = "Upload a PDF or a plain text (.txt) file."


class UploadError(Exception):
    def __init__(self, status_code: int, code: str, detail: str, extra: dict | None = None):
        super().__init__(detail)
        self.status_code = status_code
        self.code = code
        self.detail = detail
        self.extra = extra or {}  # additional fields for the response body


def limit_label() -> str:
    return f"{MAX_UPLOAD_MB:g} MB"


def detect_kind(filename: str | None, content_type: str | None) -> tuple[str, str]:
    """
    Decide whether this is a PDF or a text file. Returns (kind, content_type)
    with the content type normalized, e.g. "text/plain; charset=utf-8" becomes
    "text/plain". Raises unsupported_type for anything else.
    """
    declared = (content_type or "").split(";")[0].strip().lower()
    if declared in SUPPORTED_TYPES:
        kind = SUPPORTED_TYPES[declared]
        return kind, KIND_CONTENT_TYPE[kind]

    if declared in GENERIC_TYPES:
        extension = os.path.splitext(filename or "")[1].lower()
        if extension in EXTENSION_KINDS:
            kind = EXTENSION_KINDS[extension]
            return kind, KIND_CONTENT_TYPE[kind]
        raise UploadError(
            415,
            "unsupported_type",
            f"This file type isn't supported. {UNSUPPORTED_HINT}",
        )

    raise UploadError(
        415,
        "unsupported_type",
        f"'{declared}' files aren't supported. {UNSUPPORTED_HINT}",
    )


def check_size(contents: bytes) -> None:
    """
    `contents` is read with a cap of MAX_UPLOAD_BYTES + 1, so a file over the
    limit shows up as exactly one byte too many without loading all of it.
    """
    if len(contents) > MAX_UPLOAD_BYTES:
        raise UploadError(
            413,
            "file_too_large",
            f"This file is larger than the {limit_label()} limit. "
            "Try a smaller file, or split it into parts.",
        )
    if not contents:
        raise UploadError(400, "empty_file", "This file is empty.")


def _extract_pdf(contents: bytes) -> str:
    if b"%PDF-" not in contents[:1024]:
        raise UploadError(
            422,
            "unreadable_pdf",
            "This doesn't look like a valid PDF. It may be damaged or have the wrong file extension.",
        )
    try:
        reader = PdfReader(io.BytesIO(contents))
        if reader.is_encrypted and not reader.decrypt(""):
            raise UploadError(
                422,
                "password_protected_pdf",
                "This PDF is password-protected. Remove the password and upload it again.",
            )
        pages = [page.extract_text() or "" for page in reader.pages]
    except UploadError:
        raise
    except Exception:
        raise UploadError(
            422,
            "unreadable_pdf",
            "This PDF could not be read. It may be damaged or password-protected.",
        )
    return "\n".join(pages)


def _extract_text_file(contents: bytes) -> str:
    if contents.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = contents.decode("utf-16", errors="replace")
    else:
        if b"\x00" in contents[:8192]:
            raise UploadError(
                422,
                "unreadable_text",
                "This doesn't look like a plain text file. It seems to contain binary data.",
            )
        text = contents.decode("utf-8-sig", errors="replace")

    # Lots of replacement characters means the bytes were not text at all.
    if text and text.count("�") / len(text) > 0.1:
        raise UploadError(
            422,
            "unreadable_text",
            "This doesn't look like a plain text file. Its characters could not be read.",
        )
    return text


def extract_text(kind: str, contents: bytes) -> str:
    """
    Return the document's text, stripped. Raises no_text when the file is
    fine but has nothing in it (blank text file, or a scanned PDF with no
    text layer).
    """
    text = _extract_pdf(contents) if kind == "pdf" else _extract_text_file(contents)

    # Postgres text columns cannot hold NUL characters, and some PDFs
    # produce them, so drop them here rather than fail at insert time.
    text = text.replace("\x00", "").strip()

    if not text:
        if kind == "pdf":
            raise UploadError(
                422,
                "no_text",
                "No text could be found in this PDF. If it is a scanned document, "
                "it needs OCR first, which isn't supported yet.",
            )
        raise UploadError(422, "no_text", "This file has no readable text in it.")
    return text


def content_hash(text: str) -> str:
    """
    KV-25: fingerprint of a document's text, to detect re-uploads. Whitespace
    is collapsed first, so the same text with different line breaks or
    spacing still matches. It is computed from the extracted text rather than
    the raw file because the text is what we keep, so documents uploaded
    before this existed can be backfilled too.
    """
    normalized = " ".join(text.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
