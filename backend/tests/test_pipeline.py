"""KV-13/14/15: chunk -> embed -> store in pgvector -> find by similarity."""

import pytest
from sqlalchemy import select

from chunking import chunk_text
from embeddings import embed_text, embed_texts
from models import EMBEDDING_DIM, Chunk, Document

TEXT = (
    "KnowledgeVault lets users upload notes, PDFs, and articles, then find "
    "them later by meaning rather than exact keywords. " * 10
)


def test_embeddings_have_the_expected_size():
    vectors = embed_texts(["one", "two", "three"])
    assert len(vectors) == 3
    assert all(len(v) == EMBEDDING_DIM for v in vectors)
    assert embed_texts([]) == []
    assert len(embed_text("single")) == EMBEDDING_DIM


def test_embedding_in_batches_matches_embedding_one_by_one():
    texts = [f"sentence number {n} about topic {n % 3}" for n in range(20)]  # more than one batch
    batched = embed_texts(texts)
    assert len(batched) == len(texts)
    for text, vector in zip(texts[:3], batched[:3]):
        # The same text in a different batch can differ in the last few decimal
        # places (padding and CPU math), so compare with a small tolerance.
        assert embed_text(text) == pytest.approx(vector, abs=1e-5)


def test_chunk_embed_store_and_search(db):
    doc = Document(
        filename="pipeline_check.txt",
        content_type="text/plain",
        size_bytes=len(TEXT),
        extracted_text=TEXT,
    )
    db.add(doc)
    db.commit()

    pieces = chunk_text(TEXT)
    assert len(pieces) > 1
    for index, (piece, vector) in enumerate(zip(pieces, embed_texts(pieces))):
        db.add(Chunk(document_id=doc.id, chunk_index=index, text=piece, embedding=vector))
    db.commit()

    fetched = db.query(Document).filter(Document.id == doc.id).one()
    assert len(fetched.chunks) == len(pieces)
    assert all(c.embedding is not None for c in fetched.chunks)

    query_vector = embed_text("How do I search my notes by meaning?")
    nearest = db.execute(
        select(Chunk)
        .where(Chunk.document_id == doc.id)
        .order_by(Chunk.embedding.cosine_distance(query_vector))
        .limit(3)
    ).scalars().all()
    assert nearest, "expected at least one chunk back from similarity search"
