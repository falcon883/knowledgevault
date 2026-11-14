"""
KV-52: unusual input ends in a result or a clear message, never a crash, a
hang or a bare "Internal Server Error". Every error has the same shape,
{"detail": <message>, "code": <code>}, so the screens can show it as it is.
"""

import pytest
from helpers import minimal_pdf
from sqlalchemy.exc import OperationalError

import main
import uploads
from database import get_db
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


@pytest.fixture
def small_text_limit(monkeypatch):
    """A 300-character text limit, so 'too long' needs no huge file."""
    monkeypatch.setattr(uploads, "MAX_TEXT_CHARS", 300)
    return 300


# ---- A document with too much text ---------------------------------------


def test_text_file_with_too_much_text_is_refused(upload, db, small_text_limit):
    before = counts(db)
    assert_error(upload("check_long.txt", ("word " * 100).encode()), 422, "text_too_long", "too much text")
    assert counts(db) == before


def test_pdf_with_too_much_text_is_refused(upload, db, small_text_limit):
    before = counts(db)
    assert_error(upload("check_long.pdf", minimal_pdf("word " * 100), "application/pdf"), 422, "text_too_long")
    assert counts(db) == before


def test_text_exactly_at_the_limit_is_accepted(upload, small_text_limit):
    r = upload("check_exact_text.txt", b"x" * small_text_limit)
    assert r.status_code == 200, r.text


def test_the_text_limit_is_generous_by_default():
    # About 160 pages of text. A normal report or a short book fits.
    assert uploads.MAX_TEXT_CHARS >= 400_000


def test_error_code_is_documented():
    assert "text_too_long" in uploads.__doc__


# ---- Searches ------------------------------------------------------------


@pytest.fixture
def one_document(upload):
    r = upload("check_gardening.txt", b"Tomatoes need full sun and regular watering. Compost improves heavy clay soil.")
    assert r.status_code == 200, r.text


def test_blank_search_has_a_code_and_a_message(client):
    assert_error(client.post("/search", json={"query": "   "}), 400, "empty_query", "search for")


def test_very_long_search_is_refused_clearly(client):
    assert_error(client.post("/search", json={"query": "a" * 501}), 400, "query_too_long", "501")


def test_search_at_the_length_limit_is_accepted(client, one_document):
    query = "word " * 99 + "word"  # 499 characters
    assert len(query) <= main.MAX_QUERY_CHARS
    assert client.post("/search", json={"query": query}).status_code == 200


@pytest.mark.parametrize(
    "query",
    [
        "a",
        "ai",
        "2024",
        "26.2",
        "?!?!?!",
        "😀",
        "what is the",
        "SELECT * FROM documents; --",
        "<script>alert(1)</script>",
        "ünïcödé tëxt",
    ],
)
def test_unusual_searches_return_a_list_not_an_error(client, one_document, query):
    r = client.post("/search", json={"query": query})
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body["results"], list)
    assert body["count"] == len(body["results"])


def test_search_when_the_model_fails_gives_a_503(client, monkeypatch):
    def broken(_text):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(main, "embed_text", broken)
    assert_error(client.post("/search", json={"query": "anything"}), 503, "search_unavailable")


# ---- The database is unreachable -----------------------------------------


def test_database_down_gives_a_503_with_a_message(client, monkeypatch):
    def broken():
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))
        yield  # makes this a generator, like the real get_db

    monkeypatch.setitem(main.app.dependency_overrides, get_db, broken)
    r = client.post("/search", json={"query": "anything"})
    assert_error(r, 503, "service_unavailable", "database")
    assert r.headers["retry-after"] == "5"


# ---- Plain HTTP errors have a code too -----------------------------------


def test_missing_document_has_a_code(client):
    assert_error(client.get("/documents/999999"), 404, "not_found", "not found")


def test_someone_elses_document_is_the_same_404(client, other_client, upload):
    mine = upload("check_private.txt", b"Private notes about gardening and soil.")
    assert mine.status_code == 200, mine.text
    assert_error(other_client.get(f"/documents/{mine.json()['id']}"), 404, "not_found")


def test_unknown_address_has_a_code(client):
    assert_error(client.get("/nothing-here"), 404, "not_found")
