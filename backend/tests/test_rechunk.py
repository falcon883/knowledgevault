"""KV-38: re-chunking stored documents, and the before-and-after comparison."""

import numpy as np
import pytest
from sqlalchemy import select

import compare_chunking
import rechunk_documents
from chunking import boundary_quality, chunk_text, chunk_text_fixed
from models import Chunk, Document
from test_chunking import prose

import random

TEXT = prose(random.Random(5), 90)


def old_style(db, document_id):
    """Put a document back the way it was stored before KV-38: fixed 800-character chunks."""
    document = db.get(Document, document_id)
    pieces = chunk_text_fixed(document.extracted_text)
    document.chunks = [Chunk(chunk_index=i, text=t, embedding=[0.0] * 383 + [1.0]) for i, t in enumerate(pieces)]
    db.commit()
    return pieces


def stored(db, document_id):
    rows = db.scalars(select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.chunk_index)).all()
    return [(c.text, c.embedding) for c in rows]


@pytest.fixture
def old_document(client, upload, db):
    response = upload("kv38_old.txt", TEXT.encode())
    assert response.status_code == 200, response.text
    document_id = response.json()["id"]
    old_style(db, document_id)
    return document_id


def test_new_uploads_use_the_sentence_aware_chunks(client, upload, db):
    document_id = upload("kv38_new.txt", TEXT.encode()).json()["id"]
    assert [t for t, _ in stored(db, document_id)] == chunk_text(TEXT)


def test_rechunking_replaces_old_chunks_with_re_embedded_new_ones(old_document, db):
    before = [t for t, _ in stored(db, old_document)]
    assert before != chunk_text(TEXT)

    results = rechunk_documents.rechunk(db, [old_document])

    assert [r["status"] for r in results] == ["changed"]
    after = stored(db, old_document)
    assert [t for t, _ in after] == chunk_text(TEXT)
    assert all(vector is not None and len(vector) == 384 for _, vector in after)
    assert not any(np.allclose(vector, [0.0] * 383 + [1.0]) for _, vector in after), "chunks were re-embedded"
    assert results[0]["before"] == len(before) and results[0]["after"] == len(after)


def test_rechunking_twice_changes_nothing_the_second_time(old_document, db):
    rechunk_documents.rechunk(db, [old_document])
    first = stored(db, old_document)
    again = rechunk_documents.rechunk(db, [old_document])
    assert [r["status"] for r in again] == ["unchanged"]
    assert [t for t, _ in stored(db, old_document)] == [t for t, _ in first]


def test_a_dry_run_changes_nothing(old_document, db):
    before = [t for t, _ in stored(db, old_document)]
    results = rechunk_documents.rechunk(db, [old_document], dry_run=True)
    assert [r["status"] for r in results] == ["would change"]
    assert [t for t, _ in stored(db, old_document)] == before


def test_a_failure_leaves_that_document_as_it_was_and_the_others_get_done(client, upload, db):
    broken = upload("kv38_broken.txt", TEXT.encode()).json()["id"]
    fine = upload("kv38_fine.txt", (TEXT + " One more closing sentence.").encode()).json()["id"]
    old_style(db, broken)
    old_style(db, fine)
    before = [t for t, _ in stored(db, broken)]

    def embed(texts):
        if texts == chunk_text(TEXT):
            raise RuntimeError("model fell over")
        return [[0.1] * 384 for _ in texts]

    results = {r["id"]: r for r in rechunk_documents.rechunk(db, [broken, fine], embed=embed)}

    assert results[broken]["status"] == "failed" and "model fell over" in results[broken]["error"]
    assert [t for t, _ in stored(db, broken)] == before, "nothing was lost"
    assert results[fine]["status"] == "changed"
    assert [t for t, _ in stored(db, fine)] == chunk_text(TEXT + " One more closing sentence.")


def test_a_document_without_text_is_skipped(client, db):
    document = Document(user_id=client.user_id, filename="kv38_blank.txt", content_type="text/plain", size_bytes=0)
    db.add(document)
    db.commit()
    assert [r["status"] for r in rechunk_documents.rechunk(db, [document.id])] == ["no text"]


def test_the_command_line_reports_what_it_did(old_document, db, capsys):
    assert rechunk_documents.main(["--dry-run", "--document", str(old_document)]) == 0
    out = capsys.readouterr().out
    assert f"[{old_document}] kv38_old.txt: would change" in out
    assert "start like a sentence" in out
    assert [t for t, _ in stored(db, old_document)] != chunk_text(TEXT), "a dry run changes nothing"

    assert rechunk_documents.main(["--document", str(old_document)]) == 0
    assert "changed" in capsys.readouterr().out
    assert [t for t, _ in stored(db, old_document)] == chunk_text(TEXT)


# --- the before-and-after comparison -----------------------------------------------------


def test_the_comparison_shows_both_methods_for_each_question():
    def embed(texts):  # a tiny stand-in: each text becomes a vector of letter counts
        return [[t.lower().count(letter) for letter in "abcdefghijklmnopqrstuvwxyz"] for t in texts]

    texts = {"[1] bread.txt": TEXT, "[2] short.txt": "Plain water and flour make dough."}
    report = compare_chunking.compare(texts, ["feed the starter", "salt and yeast"], embed=embed)

    assert report.count('Query: "') == 2
    assert report.count("  BEFORE (fixed 800)\n") == 2 and report.count("  AFTER (sentence-aware)\n") == 2
    assert "[1] bread.txt" in report and "[2] short.txt" in report
    old, new = boundary_quality(chunk_text_fixed(TEXT)), boundary_quality(chunk_text(TEXT))
    assert new["clean_end"] > old["clean_end"]
    assert "% start like a sentence" in report
