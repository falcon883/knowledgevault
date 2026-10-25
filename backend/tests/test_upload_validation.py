"""KV-24: every bad upload is rejected clearly, and nothing is saved."""

import pytest
from helpers import blank_pdf, encrypted_pdf, minimal_pdf

import main
import uploads
from models import Chunk, Document


def counts(db):
    db.expire_all()
    return db.query(Document).count(), db.query(Chunk).count()


def assert_error(response, status, code, contains=None):
    body = response.json()
    assert response.status_code == status, f"expected {status}, got {response.status_code}: {body}"
    assert set(body) == {"detail", "code"}, f"error shape differs: {body}"
    assert body["code"] == code, body
    assert isinstance(body["detail"], str) and body["detail"]
    if contains:
        assert contains.lower() in body["detail"].lower(), body["detail"]


# ---- Good uploads --------------------------------------------------------


def test_plain_text_is_accepted(upload):
    r = upload("check_ok.txt", b"Plain notes about gardening and tomato plants.")
    assert r.status_code == 200, r.text
    assert r.json()["content_type"] == "text/plain"


def test_content_type_with_charset_is_normalized(upload):
    r = upload("check_charset.txt", b"Notes with a charset on the type.", "text/plain; charset=utf-8")
    assert r.status_code == 200, r.text
    assert r.json()["content_type"] == "text/plain"


def test_generic_content_type_falls_back_to_the_extension(upload):
    r = upload("check_generic.txt", b"Sent as a generic binary type.", "application/octet-stream")
    assert r.status_code == 200, r.text
    assert r.json()["content_type"] == "text/plain"


def test_pdf_text_is_extracted(upload, db):
    r = upload("check_ok.pdf", minimal_pdf("Hello KnowledgeVault PDF text"), "application/pdf")
    assert r.status_code == 200, r.text
    assert "Hello KnowledgeVault PDF text" in db.get(Document, r.json()["id"]).extracted_text


def test_health_reports_the_upload_limit(client, small_limit):
    assert client.get("/health").json()["max_upload_mb"] == 0.002


# ---- Bad uploads ---------------------------------------------------------

BAD_UPLOADS = [
    pytest.param("pic.png", b"\x89PNG....", "image/png", 415, "unsupported_type", "image/png", id="image"),
    pytest.param("data.bin", b"abc", "application/octet-stream", 415, "unsupported_type", None, id="unknown-binary"),
    pytest.param("notes.docx", b"abc", "application/vnd.openxmlformats", 415, "unsupported_type", None, id="docx"),
    pytest.param("empty.txt", b"", "text/plain", 400, "empty_file", "empty", id="empty-text"),
    pytest.param("empty.pdf", b"", "application/pdf", 400, "empty_file", None, id="empty-pdf"),
    pytest.param("blank.txt", b"   \n\t  \n", "text/plain", 422, "no_text", None, id="blank-text"),
    pytest.param("blank.pdf", blank_pdf(), "application/pdf", 422, "no_text", "scanned", id="scanned-pdf"),
    pytest.param("binary.txt", b"abc\x00\x01\x02def" * 20, "text/plain", 422, "unreadable_text", None, id="binary-as-text"),
    pytest.param("fake.pdf", b"this is just text, not a pdf", "application/pdf", 422, "unreadable_pdf", None, id="fake-pdf"),
    pytest.param("damaged.pdf", minimal_pdf("Cut off in the middle")[:60], "application/pdf", 422, "unreadable_pdf", None, id="damaged-pdf"),
    pytest.param("locked.pdf", encrypted_pdf(), "application/pdf", 422, "password_protected_pdf", None, id="password-pdf"),
]


@pytest.mark.parametrize("name, data, content_type, status, code, contains", BAD_UPLOADS)
def test_bad_upload_is_rejected_and_nothing_is_saved(upload, db, name, data, content_type, status, code, contains):
    before = counts(db)
    assert_error(upload(name, data, content_type), status, code, contains)
    assert counts(db) == before


def test_request_without_a_file(client, db):
    before = counts(db)
    assert_error(client.post("/upload"), 400, "no_file", "no file")
    assert counts(db) == before


def test_file_over_the_limit_is_rejected(upload, db, small_limit):
    before = counts(db)
    assert_error(upload("big.txt", b"a" * (small_limit + 1)), 413, "file_too_large", "larger than")
    assert counts(db) == before


def test_file_exactly_at_the_limit_is_accepted(upload, small_limit):
    r = upload("check_exact.txt", b"word " * (small_limit // 5))
    assert r.status_code == 200, r.text


def test_failure_after_validation_saves_nothing(upload, db, monkeypatch):
    def broken(_texts):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(main, "embed_texts", broken)
    before = counts(db)
    assert_error(upload("check_broken.txt", b"Valid text, broken embedder."), 500, "processing_failed")
    assert counts(db) == before


def test_error_codes_are_documented_in_uploads_module():
    # The table at the top of uploads.py is what the README points at.
    for code in (
        "no_file", "unsupported_type", "file_too_large", "empty_file", "unreadable_pdf",
        "password_protected_pdf", "unreadable_text", "no_text", "duplicate_document", "processing_failed",
    ):
        assert code in uploads.__doc__, code
