"""KV-25: uploading the same content twice is refused."""

import pytest
from helpers import minimal_pdf

from init_db import upgrade_schema
from models import Chunk, Document
from uploads import content_hash

TEXT = "Notes about composting kitchen scraps.\nKeep the pile damp and turn it weekly.\n"


def assert_duplicate(response, original_id, original_name):
    body = response.json()
    assert response.status_code == 409, f"expected 409, got {response.status_code}: {body}"
    assert set(body) == {"detail", "code", "existing"}, body
    assert body["code"] == "duplicate_document"
    assert original_name in body["detail"]
    assert set(body["existing"]) == {"id", "filename", "uploaded_at"}
    assert body["existing"]["id"] == original_id and body["existing"]["filename"] == original_name


def counts(db):
    db.expire_all()
    return db.query(Document).count(), db.query(Chunk).count()


def test_content_hash_ignores_spacing_but_not_words():
    assert content_hash("a  b\n\nc") == content_hash("a b c")
    assert content_hash("a b c") != content_hash("a b d")
    assert len(content_hash("x")) == 64


@pytest.fixture
def first(upload, db):
    r = upload("kvdup_first.txt", TEXT.encode())
    assert r.status_code == 200, r.text
    assert db.get(Document, r.json()["id"]).content_hash == content_hash(TEXT)
    return r.json()["id"]


def test_same_content_is_refused_and_nothing_is_saved(upload, db, first):
    before = counts(db)
    assert_duplicate(upload("kvdup_first.txt", TEXT.encode()), first, "kvdup_first.txt")
    assert counts(db) == before


def test_renamed_and_respaced_copies_are_caught(upload, first):
    respaced = "Notes about composting   kitchen scraps. Keep the pile damp\r\nand turn it weekly.  "
    assert_duplicate(upload("kvdup_renamed.txt", respaced.encode()), first, "kvdup_first.txt")
    assert_duplicate(
        upload("kvdup_generic.txt", TEXT.encode(), "application/octet-stream"), first, "kvdup_first.txt"
    )


def test_different_content_is_accepted(upload, first):
    assert upload("kvdup_other.txt", b"Completely different notes about bicycle maintenance.").status_code == 200


def test_same_filename_with_different_content_is_accepted(upload, first):
    assert upload("kvdup_first.txt", b"Different words entirely, same file name.").status_code == 200


def test_pdfs_are_covered_too(upload):
    pdf = minimal_pdf("Quarterly gardening budget review")
    original = upload("kvdup_budget.pdf", pdf, "application/pdf")
    assert original.status_code == 200, original.text
    assert_duplicate(
        upload("kvdup_budget_copy.pdf", pdf, "application/pdf"), original.json()["id"], "kvdup_budget.pdf"
    )


def test_allow_duplicate_stores_a_second_copy(upload, first):
    forced = upload("kvdup_forced.txt", TEXT.encode(), allow_duplicate="true")
    assert forced.status_code == 200, forced.text
    assert forced.json()["id"] != first
    # The oldest copy is the one reported from now on.
    assert_duplicate(upload("kvdup_again.txt", TEXT.encode()), first, "kvdup_first.txt")


def test_content_can_be_uploaded_again_once_every_copy_is_deleted(client, upload, first):
    forced = upload("kvdup_forced.txt", TEXT.encode(), allow_duplicate="true").json()["id"]
    assert client.delete(f"/documents/{first}").status_code == 200
    assert_duplicate(upload("kvdup_after_delete.txt", TEXT.encode()), forced, "kvdup_forced.txt")
    assert client.delete(f"/documents/{forced}").status_code == 200
    assert upload("kvdup_again.txt", TEXT.encode()).status_code == 200


def test_documents_from_before_the_hash_existed_are_backfilled(upload, db):
    legacy = Document(
        filename="kvdup_legacy.txt", content_type="text/plain", size_bytes=10,
        extracted_text="Legacy   notes on\nsourdough starters.", content_hash=None,
    )
    blank = Document(filename="kvdup_blank.txt", content_type="text/plain", size_bytes=0, extracted_text=None)
    db.add_all([legacy, blank])
    db.commit()

    assert upgrade_schema() >= 1
    db.expire_all()
    assert legacy.content_hash == content_hash("Legacy notes on sourdough starters.")
    assert blank.content_hash is None, "a document with no text should stay unhashed"
    assert upgrade_schema() == 0, "upgrade_schema should be safe to run again"
    assert_duplicate(
        upload("kvdup_legacy_copy.txt", b"Legacy notes on sourdough starters."), legacy.id, "kvdup_legacy.txt"
    )
