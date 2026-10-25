"""KV-26: GET /documents filters, GET /tags and GET /documents/{id}."""

from datetime import datetime, timedelta, timezone

import pytest

from models import EMBEDDING_DIM, Chunk, Document

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


@pytest.fixture
def library(db):
    """The five documents above, created directly with tags and dates set by hand."""
    ids = {}
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
            db.add(Chunk(document_id=doc.id, chunk_index=i, text=text[:20], embedding=[0.0] * EMBEDDING_DIM))
        ids[filename] = doc.id
    db.commit()
    return ids


@pytest.fixture
def names(library):
    """names(response) -> the test documents in the response, as filenames, in order."""
    by_id = {v: k for k, v in library.items()}

    def _names(response):
        assert response.status_code == 200, response.text
        return [by_id[d["id"]] for d in response.json() if d["id"] in by_id]

    return _names


NEWEST_FIRST = ["kvt_elder.txt", "kvt_date.txt", "kvt_cherry.pdf", "kvt_Apple.txt", "kvt_banana.txt"]


# ---- GET /documents ------------------------------------------------------


def test_default_order_and_fields_are_unchanged(client, library, names):
    r = client.get("/documents")
    assert names(r) == NEWEST_FIRST
    banana = next(d for d in r.json() if d["id"] == library["kvt_banana.txt"])
    assert set(banana) == {
        "id", "filename", "content_type", "size_bytes", "uploaded_at", "tags", "summary", "chunk_count",
    }
    assert banana["chunk_count"] == 2 and banana["summary"] == "About kvt_banana.txt"
    assert next(d for d in r.json() if d["id"] == library["kvt_date.txt"])["tags"] is None


def test_sort(client, names):
    assert names(client.get("/documents?sort=newest")) == NEWEST_FIRST
    assert names(client.get("/documents?sort=oldest")) == list(reversed(NEWEST_FIRST))
    # A to Z ignoring case: Apple (capital A) sits before banana.
    assert names(client.get("/documents?sort=name")) == [
        "kvt_Apple.txt", "kvt_banana.txt", "kvt_cherry.pdf", "kvt_date.txt", "kvt_elder.txt",
    ]
    assert client.get("/documents?sort=random").status_code == 422


def test_tag_filter(client, names):
    both_recipes = ["kvt_Apple.txt", "kvt_banana.txt"]
    assert names(client.get(f"/documents?tag={PREFIX}recipes")) == both_recipes
    assert names(client.get(f"/documents?tag={PREFIX.upper()}RECIPES")) == both_recipes  # ignores case
    assert names(client.get(f"/documents?tag=%20{PREFIX}fruit%20")) == [  # ignores padding
        "kvt_elder.txt", "kvt_cherry.pdf", "kvt_banana.txt",
    ]
    # Whole tag only: "recipe" is not "recipes", and "recipes" is not "recipes-extra".
    assert names(client.get(f"/documents?tag={PREFIX}recipe")) == []
    assert names(client.get(f"/documents?tag={PREFIX}recipes-extra")) == ["kvt_elder.txt"]
    assert names(client.get("/documents?tag=no-such-tag-anywhere")) == []


@pytest.mark.parametrize("blank", ["", "%20%20"])
def test_blank_tag_is_ignored(client, names, blank):
    assert names(client.get(f"/documents?tag={blank}")) == NEWEST_FIRST


@pytest.mark.parametrize(
    "since, expected",
    [
        ("2026-10-17", ["kvt_elder.txt"]),
        # A date with no time is the start of that day (UTC), so a 12:00 upload that day counts.
        ("2026-10-16", ["kvt_elder.txt", "kvt_date.txt"]),
        ("2026-10-11", ["kvt_elder.txt", "kvt_date.txt", "kvt_cherry.pdf"]),
        # At or after: exactly 12:00:00 counts, one second later does not.
        ("2026-10-11T12:00:00Z", ["kvt_elder.txt", "kvt_date.txt", "kvt_cherry.pdf"]),
        ("2026-10-11T12:00:01Z", ["kvt_elder.txt", "kvt_date.txt"]),
        # No zone is read as UTC.
        ("2026-10-11T12:00:01", ["kvt_elder.txt", "kvt_date.txt"]),
        # 12:00 at UTC+5 is 07:00 UTC, so cherry (12:00 UTC) is in.
        ("2026-10-11T12:00:00%2B05:00", ["kvt_elder.txt", "kvt_date.txt", "kvt_cherry.pdf"]),
        ("2030-01-01", []),
    ],
)
def test_since_filter(client, names, since, expected):
    assert names(client.get(f"/documents?since={since}")) == expected


def test_since_rejects_garbage(client):
    assert client.get("/documents?since=yesterday").status_code == 422


def test_filters_combine(client, names):
    assert names(client.get(f"/documents?tag={PREFIX}fruit&since=2026-10-05&sort=oldest")) == [
        "kvt_cherry.pdf", "kvt_elder.txt",
    ]
    assert names(client.get(f"/documents?tag={PREFIX}fruit&since=2026-10-16&sort=name")) == ["kvt_elder.txt"]


# ---- GET /tags -----------------------------------------------------------


def test_tags_are_counted_case_insensitively(client, library):
    r = client.get("/tags")
    assert r.status_code == 200
    ours = {t["tag"].lower(): t["count"] for t in r.json() if t["tag"].lower().startswith(PREFIX)}
    assert ours == {
        f"{PREFIX}recipes": 2,  # "recipes" and "Recipes" are one tag
        f"{PREFIX}fruit": 3,  # banana "Fruit", cherry "fruit", elder "Fruit " (trailing space)
        f"{PREFIX}baking": 1,
        f"{PREFIX}recipes-extra": 1,
    }


def test_tags_are_ordered_unique_and_clean(client, library):
    tags = client.get("/tags").json()
    assert all(set(t) == {"tag", "count"} and t["tag"] == t["tag"].strip() and t["tag"] for t in tags)
    order = [(-t["count"], t["tag"].lower()) for t in tags]
    assert order == sorted(order), "tags not ordered by count then name"
    lowered = [t["tag"].lower() for t in tags]
    assert len(lowered) == len(set(lowered)), "duplicate tags"


def test_tags_limit(client, library):
    everything = client.get("/tags").json()
    assert client.get("/tags?limit=1").json() == everything[:1]
    assert len(client.get("/tags?limit=2").json()) == min(2, len(everything))
    assert client.get("/tags?limit=0").status_code == 422
    assert client.get("/tags?limit=501").status_code == 422


# ---- GET /documents/{id} -------------------------------------------------

FULL_TEXT = "Banana bread. " * 50


def test_document_detail(client, library):
    r = client.get(f"/documents/{library['kvt_banana.txt']}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {
        "id", "filename", "content_type", "size_bytes", "uploaded_at", "tags", "summary",
        "chunk_count", "extracted_text", "text_length", "truncated",
    }
    assert body["filename"] == "kvt_banana.txt" and body["chunk_count"] == 2
    assert body["extracted_text"] == FULL_TEXT
    assert body["text_length"] == len(FULL_TEXT) and body["truncated"] is False


def test_detail_agrees_with_the_list(client, library):
    banana = library["kvt_banana.txt"]
    listed = next(d for d in client.get("/documents").json() if d["id"] == banana)
    detail = client.get(f"/documents/{banana}").json()
    assert {k: detail[k] for k in listed} == listed


def test_max_chars_truncates_for_previews(client, library):
    banana = library["kvt_banana.txt"]
    body = client.get(f"/documents/{banana}?max_chars=30").json()
    assert body["extracted_text"] == FULL_TEXT[:30]
    assert body["text_length"] == len(FULL_TEXT) and body["truncated"] is True
    # Exactly the full length, or more, is not truncated.
    for limit in (len(FULL_TEXT), len(FULL_TEXT) + 100):
        body = client.get(f"/documents/{banana}?max_chars={limit}").json()
        assert body["extracted_text"] == FULL_TEXT and body["truncated"] is False


def test_detail_of_an_untagged_document(client, library):
    assert client.get(f"/documents/{library['kvt_date.txt']}").json()["tags"] is None


def test_detail_errors(client, library):
    missing = client.get("/documents/99999999")
    assert missing.status_code == 404 and "99999999" in missing.json()["detail"]
    assert client.get("/documents/abc").status_code == 422
    banana = library["kvt_banana.txt"]
    assert client.get(f"/documents/{banana}?max_chars=0").status_code == 422
    assert client.get(f"/documents/{banana}?max_chars=1000001").status_code == 422


def test_delete_still_works_beside_the_detail_route(client, library):
    doc_id = library["kvt_date.txt"]
    assert client.delete(f"/documents/{doc_id}").status_code == 200
    assert client.get(f"/documents/{doc_id}").status_code == 404
