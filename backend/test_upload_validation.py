"""
Manual check for KV-24: upload validation.

    python test_upload_validation.py

Sends good and bad files to POST /upload and confirms each bad one is
rejected with the right status, the same error shape, a specific message,
and that nothing is saved when an upload fails. Uses a tiny size limit (set
below) so the "too large" case doesn't need a big file. Cleans up after
itself.

Requires Postgres with pgvector running (see README.md). Embedding is real
on the happy-path uploads, so the first run downloads the model.
"""

import logging
import os

# Must be set before uploads.py is imported: a 2 KB limit for this test.
os.environ["MAX_UPLOAD_MB"] = "0.002"

from fastapi.testclient import TestClient  # noqa: E402
from pypdf import PdfWriter  # noqa: E402

import main  # noqa: E402
import uploads  # noqa: E402
from database import Base, SessionLocal, engine  # noqa: E402
from models import Chunk, Document  # noqa: E402

Base.metadata.create_all(bind=engine)
client = TestClient(app=main.app)
db = SessionLocal()

LIMIT = uploads.MAX_UPLOAD_BYTES
assert LIMIT == int(0.002 * 1024 * 1024), LIMIT


def counts():
    db.expire_all()
    return db.query(Document).count(), db.query(Chunk).count()


def minimal_pdf(text: str) -> bytes:
    """A one-page PDF with `text` on it, built by hand so no extra library is needed."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n"
    ).encode()
    return out


def blank_pdf() -> bytes:
    """A valid PDF whose only page has no text, like a scanned document."""
    import io

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def upload(name, data, content_type):
    return client.post("/upload", files={"file": (name, data, content_type)})


def expect_error(response, status, code, contains=None):
    body = response.json()
    assert response.status_code == status, f"expected {status}, got {response.status_code}: {body}"
    assert set(body) == {"detail", "code"}, f"error shape differs: {body}"
    assert body["code"] == code, f"expected code {code}, got {body}"
    assert isinstance(body["detail"], str) and body["detail"], body
    if contains:
        assert contains.lower() in body["detail"].lower(), f"{contains!r} not in {body['detail']!r}"
    return body


created = []
try:
    # ---- Good uploads still work -------------------------------------------
    r = upload("check_ok.txt", b"Plain notes about gardening and tomato plants.", "text/plain")
    assert r.status_code == 200, r.text
    created.append(r.json()["id"])
    assert r.json()["content_type"] == "text/plain"

    r = upload("check_charset.txt", b"Notes with a charset on the type.", "text/plain; charset=utf-8")
    assert r.status_code == 200, r.text
    created.append(r.json()["id"])
    assert r.json()["content_type"] == "text/plain", "content type should be normalized"

    r = upload("check_generic.txt", b"Sent as a generic binary type.", "application/octet-stream")
    assert r.status_code == 200, r.text
    created.append(r.json()["id"])
    assert r.json()["content_type"] == "text/plain", "type should come from the .txt extension"

    r = upload("check_ok.pdf", minimal_pdf("Hello KnowledgeVault PDF text"), "application/pdf")
    assert r.status_code == 200, r.text
    created.append(r.json()["id"])
    stored = db.get(Document, r.json()["id"])
    assert "Hello KnowledgeVault PDF text" in stored.extracted_text
    print("Good uploads accepted: txt, txt with charset, generic type by extension, pdf")

    r = client.get("/health")
    assert r.json()["max_upload_mb"] == 0.002, r.json()
    print("/health reports the upload limit")

    # ---- Bad uploads: rejected, same shape, nothing saved -------------------
    before = counts()

    expect_error(client.post("/upload"), 400, "no_file", "no file")
    expect_error(upload("pic.png", b"\x89PNG....", "image/png"), 415, "unsupported_type", "image/png")
    expect_error(upload("data.bin", b"abc", "application/octet-stream"), 415, "unsupported_type")
    expect_error(upload("notes.docx", b"abc", "application/vnd.openxmlformats"), 415, "unsupported_type")

    expect_error(upload("empty.txt", b"", "text/plain"), 400, "empty_file", "empty")
    expect_error(upload("empty.pdf", b"", "application/pdf"), 400, "empty_file")

    big = b"a" * (LIMIT + 1)
    expect_error(upload("big.txt", big, "text/plain"), 413, "file_too_large", "larger than")
    # Exactly at the limit is fine, one byte over is not (checked above).
    exact = upload("check_exact.txt", b"word " * (LIMIT // 5), "text/plain")
    assert exact.status_code == 200, exact.text
    created.append(exact.json()["id"])
    before = (before[0] + 1, before[1] + exact.json()["chunk_count"])

    expect_error(upload("blank.txt", b"   \n\t  \n", "text/plain"), 422, "no_text")
    expect_error(upload("blank.pdf", blank_pdf(), "application/pdf"), 422, "no_text", "scanned")
    expect_error(upload("binary.txt", b"abc\x00\x01\x02def" * 20, "text/plain"), 422, "unreadable_text")
    expect_error(upload("fake.pdf", b"this is just text, not a pdf", "application/pdf"), 422, "unreadable_pdf")
    damaged = minimal_pdf("Cut off in the middle")[:60]
    expect_error(upload("damaged.pdf", damaged, "application/pdf"), 422, "unreadable_pdf")

    try:
        import io

        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        writer.encrypt("secret", algorithm="RC4-128")
        buffer = io.BytesIO()
        writer.write(buffer)
        expect_error(upload("locked.pdf", buffer.getvalue(), "application/pdf"), 422, "password_protected_pdf")
        print("Password-protected PDF rejected")
    except (ImportError, NotImplementedError):
        print("(skipped password-protected PDF case: encryption not available here)")

    assert counts() == before, f"rows were saved by failed uploads: {before} -> {counts()}"
    print("All bad uploads rejected with the same {detail, code} shape; nothing saved")

    # ---- A failure after validation also leaves nothing behind --------------
    original = main.embed_texts

    def broken(_texts):
        raise RuntimeError("model unavailable")

    main.embed_texts = broken
    app_log = logging.getLogger("knowledgevault")
    app_log.disabled = True  # the error is expected here, keep the output clean
    try:
        expect_error(upload("check_broken.txt", b"Valid text, broken embedder.", "text/plain"), 500, "processing_failed")
    finally:
        main.embed_texts = original
        app_log.disabled = False
    assert counts() == before, "failed processing left rows behind"
    print("Processing failure returns 500 processing_failed and saves nothing")

    # ---- Search still only needs the original, unchanged endpoints ----------
    assert client.post("/search", json={"query": "tomato plants", "limit": 3, "min_score": 0}).status_code == 200
finally:
    for doc_id in created:
        doc = db.get(Document, doc_id)
        if doc is not None:
            db.delete(doc)
    db.commit()
    db.close()

print("KV-24 upload validation passed.")
