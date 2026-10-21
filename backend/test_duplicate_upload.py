"""
Manual check for KV-25: duplicate upload detection.

    python test_duplicate_upload.py

Uploads a file, then confirms that uploading the same content again is
refused with 409 duplicate_document (pointing at the existing document),
even with a different file name or different spacing; that nothing is saved
by the refused upload; that allow_duplicate=true overrides it; and that
documents stored before the content_hash column existed are backfilled by
init_db.upgrade_schema(). Cleans up after itself.

Requires Postgres with pgvector running (see README.md).
"""

import logging

from fastapi.testclient import TestClient
from pypdf import PdfWriter  # noqa: F401  (keeps the import check same as the other tests)

import main
from database import Base, SessionLocal, engine
from init_db import upgrade_schema
from models import Chunk, Document
from uploads import content_hash

Base.metadata.create_all(bind=engine)
upgrade_schema()
client = TestClient(app=main.app)
db = SessionLocal()


def counts():
    db.expire_all()
    return db.query(Document).count(), db.query(Chunk).count()


def upload(name, data, content_type="text/plain", **params):
    return client.post("/upload", files={"file": (name, data, content_type)}, params=params)


def minimal_pdf(text: str) -> bytes:
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


def expect_duplicate(response, original_id, original_name):
    body = response.json()
    assert response.status_code == 409, f"expected 409, got {response.status_code}: {body}"
    assert set(body) == {"detail", "code", "existing"}, f"shape differs: {body}"
    assert body["code"] == "duplicate_document"
    assert isinstance(body["detail"], str) and original_name in body["detail"], body["detail"]
    existing = body["existing"]
    assert set(existing) == {"id", "filename", "uploaded_at"}, existing
    assert existing["id"] == original_id and existing["filename"] == original_name, existing


TEXT = "Notes about composting kitchen scraps.\nKeep the pile damp and turn it weekly.\n"
created = []
try:
    # ---- The fingerprint ----------------------------------------------------
    assert content_hash("a  b\n\nc") == content_hash("a b c")
    assert content_hash("a b c") != content_hash("a b d")
    assert len(content_hash("x")) == 64
    print("content_hash ignores spacing and line breaks, but not words")

    # ---- First upload works and stores the hash -----------------------------
    first = upload("kvdup_first.txt", TEXT.encode())
    assert first.status_code == 200, first.text
    first_id = first.json()["id"]
    created.append(first_id)
    assert db.get(Document, first_id).content_hash == content_hash(TEXT)
    print("First upload accepted and fingerprinted")

    # ---- Same content again is refused, nothing saved -----------------------
    before = counts()
    expect_duplicate(upload("kvdup_first.txt", TEXT.encode()), first_id, "kvdup_first.txt")
    # Different name, different spacing and line breaks: still the same document.
    respaced = "Notes about composting   kitchen scraps. Keep the pile damp\r\nand turn it weekly.  "
    expect_duplicate(upload("kvdup_renamed.txt", respaced.encode()), first_id, "kvdup_first.txt")
    # Generic content type, judged by extension: still caught.
    expect_duplicate(
        upload("kvdup_generic.txt", TEXT.encode(), "application/octet-stream"), first_id, "kvdup_first.txt"
    )
    assert counts() == before, "a refused duplicate saved rows"
    print("Re-upload refused with 409 duplicate_document (renamed and respaced too); nothing saved")

    # ---- Different content is fine ------------------------------------------
    other = upload("kvdup_other.txt", b"Completely different notes about bicycle maintenance.")
    assert other.status_code == 200, other.text
    created.append(other.json()["id"])
    print("Different content accepted")

    # ---- PDFs are covered too -----------------------------------------------
    pdf = minimal_pdf("Quarterly gardening budget review")
    p1 = upload("kvdup_budget.pdf", pdf, "application/pdf")
    assert p1.status_code == 200, p1.text
    created.append(p1.json()["id"])
    expect_duplicate(upload("kvdup_budget_copy.pdf", pdf, "application/pdf"), p1.json()["id"], "kvdup_budget.pdf")
    print("PDF re-upload refused")

    # ---- allow_duplicate overrides ------------------------------------------
    forced = upload("kvdup_forced.txt", TEXT.encode(), allow_duplicate="true")
    assert forced.status_code == 200, forced.text
    created.append(forced.json()["id"])
    assert forced.json()["id"] != first_id
    # The oldest copy is the one reported from now on.
    expect_duplicate(upload("kvdup_again.txt", TEXT.encode()), first_id, "kvdup_first.txt")
    print("allow_duplicate=true stores a second copy; the original is still the one reported")

    # ---- Deleting every copy makes the content uploadable again -------------
    assert client.delete(f"/documents/{first_id}").status_code == 200
    # The forced copy is still there, so it is now the existing document.
    expect_duplicate(upload("kvdup_after_delete.txt", TEXT.encode()), forced.json()["id"], "kvdup_forced.txt")
    assert client.delete(f"/documents/{forced.json()['id']}").status_code == 200
    again = upload("kvdup_again.txt", TEXT.encode())
    assert again.status_code == 200, again.text
    created.append(again.json()["id"])
    print("After deleting all copies, the content can be uploaded again")

    # ---- Upgrade / backfill for documents stored before KV-25 ---------------
    legacy = Document(
        filename="kvdup_legacy.txt",
        content_type="text/plain",
        size_bytes=10,
        extracted_text="Legacy   notes on\nsourdough starters.",
        content_hash=None,
    )
    blank = Document(
        filename="kvdup_blank.txt", content_type="text/plain", size_bytes=0, extracted_text=None
    )
    db.add_all([legacy, blank])
    db.commit()
    created += [legacy.id, blank.id]

    filled = upgrade_schema()
    assert filled >= 1, filled
    db.expire_all()
    assert db.get(Document, legacy.id).content_hash == content_hash("Legacy notes on sourdough starters.")
    assert db.get(Document, blank.id).content_hash is None, "a document with no text should stay unhashed"
    assert upgrade_schema() == 0, "upgrade_schema should be safe to run again"
    expect_duplicate(
        upload("kvdup_legacy_copy.txt", b"Legacy notes on sourdough starters."), legacy.id, "kvdup_legacy.txt"
    )
    print("Documents from before KV-25 are backfilled and count as duplicates; re-running is a no-op")
finally:
    logging.disable(logging.NOTSET)
    db.rollback()
    for doc_id in created:
        doc = db.get(Document, doc_id)
        if doc is not None:
            db.delete(doc)
    db.commit()
    db.close()

print("KV-25 duplicate detection passed.")
