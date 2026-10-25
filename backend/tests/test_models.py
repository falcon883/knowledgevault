"""KV-7: the schema round-trips correctly."""

from models import Chunk, Document


def test_document_and_chunk_round_trip(db):
    doc = Document(
        filename="sample.pdf",
        content_type="application/pdf",
        size_bytes=1426,
        extracted_text="KnowledgeVault KV-6 test PDF.\nThis line should be extracted by pypdf.",
    )
    db.add(doc)
    db.commit()
    db.add(Chunk(document_id=doc.id, chunk_index=0, text=doc.extracted_text))
    db.commit()

    fetched = db.query(Document).filter(Document.id == doc.id).one()
    assert len(fetched.chunks) == 1
    assert fetched.chunks[0].text == doc.extracted_text
    assert fetched.uploaded_at is not None


def test_deleting_a_document_deletes_its_chunks(db):
    doc = Document(filename="gone.txt", content_type="text/plain", size_bytes=3, extracted_text="abc")
    db.add(doc)
    db.commit()
    db.add(Chunk(document_id=doc.id, chunk_index=0, text="abc"))
    db.commit()
    doc_id = doc.id

    db.delete(doc)
    db.commit()
    assert db.query(Chunk).filter(Chunk.document_id == doc_id).count() == 0
