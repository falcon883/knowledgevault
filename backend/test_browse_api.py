"""
Manual check for KV-26: browse and preview API.

    python test_browse_api.py

Covers GET /documents (tag, since, sort filters), GET /tags and
GET /documents/{id}. Creates its own documents directly in the database
(tags and upload dates set by hand, so no embedding model is needed), checks
them, and deletes them again. Other documents already in the database are
ignored: every check looks only at the test documents.

Requires Postgres with pgvector running (see README.md).
"""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

import main
from database import Base, SessionLocal, engine
from models import EMBEDDING_DIM, Chunk, Document

Base.metadata.create_all(bind=engine)
client = TestClient(app=main.app)
db = SessionLocal()

BASE = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
PREFIX = "kvtest-"

# (filename, tags, days after BASE, number of chunks, text)
SPEC = [
    ("kvt_banana.txt", f"{PREFIX}recipes, {PREFIX}Fruit", 0, 2, "Banana bread. " * 50),
    ("kvt_Apple.txt", f"{PREFIX}Recipes,{PREFIX}baking", 5, 1, "Apple pie notes."),
    ("kvt_cherry.pdf", f"{PREFIX}fruit", 10, 1, "Cherry facts."),
    ("kvt_date.txt", None, 15, 1, "No tags on this one."),
    ("kvt_elder.txt", f"{PREFIX}recipes-extra, , {PREFIX}Fruit ", 20, 1, "Elderberry wine."),
]

ids = {}
try:
    for filename, tags, days, n_chunks, text in SPEC:
        doc = Document(
            filename=filename,
            content_type="application/pdf" if filename.endswith(".pdf") else "text/plain",
            size_bytes=len(text),
            extracted_text=text,
            uploaded_at=BASE + timedelta(days=days),
            tags=tags,
            summary=f"About {filename}",
        )
        db.add(doc)
        db.flush()
        for i in range(n_chunks):
            db.add(Chunk(document_id=doc.id, chunk_index=i, text=text[:20] or "x", embedding=[0.0] * EMBEDDING_DIM))
        ids[filename] = doc.id
    db.commit()

    mine = set(ids.values())
    by_id = {v: k for k, v in ids.items()}

    def names(response):
        """Test documents in the response, as filenames, in order."""
        assert response.status_code == 200, response.text
        return [by_id[d["id"]] for d in response.json() if d["id"] in mine]

    # ---- GET /documents: unchanged defaults ---------------------------------
    r = client.get("/documents")
    assert names(r) == ["kvt_elder.txt", "kvt_date.txt", "kvt_cherry.pdf", "kvt_Apple.txt", "kvt_banana.txt"]
    first = next(d for d in r.json() if d["id"] == ids["kvt_banana.txt"])
    assert set(first) == {
        "id", "filename", "content_type", "size_bytes", "uploaded_at", "tags", "summary", "chunk_count",
    }, set(first)
    assert first["chunk_count"] == 2 and first["summary"] == "About kvt_banana.txt"
    assert "extracted_text" not in first
    assert next(d for d in r.json() if d["id"] == ids["kvt_date.txt"])["tags"] is None
    print("GET /documents: default order and fields unchanged")

    # ---- sort ---------------------------------------------------------------
    assert names(client.get("/documents?sort=newest")) == names(r)
    assert names(client.get("/documents?sort=oldest")) == list(reversed(names(r)))
    # A to Z ignoring case: Apple (capital A) sits before banana.
    assert names(client.get("/documents?sort=name")) == [
        "kvt_Apple.txt", "kvt_banana.txt", "kvt_cherry.pdf", "kvt_date.txt", "kvt_elder.txt",
    ]
    assert client.get("/documents?sort=random").status_code == 422
    print("GET /documents: sort newest, oldest, name (case-insensitive), bad value rejected")

    # ---- tag ----------------------------------------------------------------
    assert names(client.get(f"/documents?tag={PREFIX}recipes")) == ["kvt_Apple.txt", "kvt_banana.txt"]
    assert names(client.get(f"/documents?tag={PREFIX.upper()}RECIPES")) == ["kvt_Apple.txt", "kvt_banana.txt"]
    assert names(client.get(f"/documents?tag=%20{PREFIX}fruit%20")) == [
        "kvt_elder.txt", "kvt_cherry.pdf", "kvt_banana.txt",
    ]
    # Whole-tag matches only: "recipes" must not match "recipes-extra" or part of a word.
    assert names(client.get(f"/documents?tag={PREFIX}recipe")) == []
    assert names(client.get(f"/documents?tag={PREFIX}recipes-extra")) == ["kvt_elder.txt"]
    assert names(client.get("/documents?tag=no-such-tag-anywhere")) == []
    # A blank tag is ignored.
    assert names(client.get("/documents?tag=")) == names(r)
    assert names(client.get("/documents?tag=%20%20")) == names(r)
    print("GET /documents: tag filter (case-insensitive, whole tag only, blank ignored)")

    # ---- since --------------------------------------------------------------
    assert names(client.get("/documents?since=2026-10-17")) == ["kvt_elder.txt"]
    # A date with no time means the start of that day (UTC), so a document
    # uploaded at 12:00 that day is included.
    assert names(client.get("/documents?since=2026-10-16")) == ["kvt_elder.txt", "kvt_date.txt"]
    assert names(client.get("/documents?since=2026-10-11")) == ["kvt_elder.txt", "kvt_date.txt", "kvt_cherry.pdf"]
    # At or after: exactly 12:00:00 counts, one second later does not.
    assert names(client.get("/documents?since=2026-10-11T12:00:00Z")) == ["kvt_elder.txt", "kvt_date.txt", "kvt_cherry.pdf"]
    assert names(client.get("/documents?since=2026-10-11T12:00:01Z")) == ["kvt_elder.txt", "kvt_date.txt"]
    # No zone is read as UTC.
    assert names(client.get("/documents?since=2026-10-11T12:00:01")) == ["kvt_elder.txt", "kvt_date.txt"]
    # A zone offset is respected: 12:00 at UTC+5 is 07:00 UTC, so cherry is in.
    assert names(client.get("/documents?since=2026-10-11T12:00:00%2B05:00")) == ["kvt_elder.txt", "kvt_date.txt", "kvt_cherry.pdf"]
    assert names(client.get("/documents?since=2030-01-01")) == []
    assert client.get("/documents?since=yesterday").status_code == 422
    print("GET /documents: since filter (date, datetime, zone offset, bad value rejected)")

    # ---- combined -----------------------------------------------------------
    assert names(client.get(f"/documents?tag={PREFIX}fruit&since=2026-10-05&sort=oldest")) == [
        "kvt_cherry.pdf", "kvt_elder.txt",
    ]
    assert names(client.get(f"/documents?tag={PREFIX}fruit&since=2026-10-16&sort=name")) == ["kvt_elder.txt"]
    print("GET /documents: filters combine")

    # ---- GET /tags ----------------------------------------------------------
    r = client.get("/tags")
    assert r.status_code == 200, r.text
    tags = {t["tag"].lower(): t["count"] for t in r.json() if t["tag"].lower().startswith(PREFIX)}
    assert tags == {
        f"{PREFIX}recipes": 2,       # "recipes" and "Recipes" are one tag
        f"{PREFIX}fruit": 3,         # banana "Fruit", cherry "fruit", elder "Fruit " (trailing space)
        f"{PREFIX}baking": 1,
        f"{PREFIX}recipes-extra": 1,
    }, tags
    assert all(set(t) == {"tag", "count"} and t["tag"] == t["tag"].strip() and t["tag"] for t in r.json())
    # Most common first, ties A to Z.
    order = [(-t["count"], t["tag"].lower()) for t in r.json()]
    assert order == sorted(order), "tags not ordered by count then name"
    # Each tag is listed once.
    lowered = [t["tag"].lower() for t in r.json()]
    assert len(lowered) == len(set(lowered)), "duplicate tags in /tags"
    assert client.get("/tags?limit=1").json() == r.json()[:1]
    assert len(client.get("/tags?limit=2").json()) == min(2, len(r.json()))
    assert client.get("/tags?limit=0").status_code == 422
    assert client.get("/tags?limit=501").status_code == 422
    print("GET /tags: counts, case-insensitive merge, order, limit")

    # ---- GET /documents/{id} ------------------------------------------------
    banana = ids["kvt_banana.txt"]
    r = client.get(f"/documents/{banana}")
    assert r.status_code == 200, r.text
    body = r.json()
    full_text = "Banana bread. " * 50
    assert set(body) == {
        "id", "filename", "content_type", "size_bytes", "uploaded_at", "tags", "summary",
        "chunk_count", "extracted_text", "text_length", "truncated",
    }, set(body)
    assert body["id"] == banana and body["filename"] == "kvt_banana.txt"
    assert body["chunk_count"] == 2
    assert body["extracted_text"] == full_text
    assert body["text_length"] == len(full_text) and body["truncated"] is False

    body = client.get(f"/documents/{banana}?max_chars=30").json()
    assert body["extracted_text"] == full_text[:30]
    assert body["text_length"] == len(full_text) and body["truncated"] is True

    # Exactly the full length, or more, is not truncated.
    for limit in (len(full_text), len(full_text) + 100):
        body = client.get(f"/documents/{banana}?max_chars={limit}").json()
        assert body["extracted_text"] == full_text and body["truncated"] is False

    # The list fields agree with the list endpoint.
    listed = next(d for d in client.get("/documents").json() if d["id"] == banana)
    detail = client.get(f"/documents/{banana}").json()
    assert {k: detail[k] for k in listed} == listed

    # A document with no tags still works.
    assert client.get(f"/documents/{ids['kvt_date.txt']}").json()["tags"] is None

    missing = client.get("/documents/99999999")
    assert missing.status_code == 404 and isinstance(missing.json()["detail"], str)
    assert "99999999" in missing.json()["detail"]
    assert client.get("/documents/abc").status_code == 422
    assert client.get(f"/documents/{banana}?max_chars=0").status_code == 422
    assert client.get(f"/documents/{banana}?max_chars=1000001").status_code == 422
    print("GET /documents/{id}: full text, max_chars, truncated flag, 404, bad input")

    # ---- Delete still works with the new detail route -----------------------
    assert client.delete(f"/documents/{ids['kvt_date.txt']}").status_code == 200
    assert client.get(f"/documents/{ids['kvt_date.txt']}").status_code == 404
finally:
    db.rollback()
    for doc_id in ids.values():
        doc = db.get(Document, doc_id)
        if doc is not None:
            db.delete(doc)
    db.commit()
    db.close()

print("KV-26 browse and preview API passed.")
