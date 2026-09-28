"""
Quick manual check that the schema round-trips correctly. Not a pytest
suite yet (that's Section 6.4 / a later sprint) - just proof the models
work before the team builds on top of them.

    python test_models.py
"""

from database import Base, SessionLocal, engine
from models import Chunk, Document

# Use a throwaway in-memory-style setup for this check: create tables,
# insert, query, then clean up.
Base.metadata.create_all(bind=engine)

db = SessionLocal()

doc = Document(
    filename="sample.pdf",
    content_type="application/pdf",
    size_bytes=1426,
    extracted_text="KnowledgeVault KV-6 test PDF.\nThis line should be extracted by pypdf.",
)
db.add(doc)
db.commit()
db.refresh(doc)
print("Inserted document:", doc)

chunk = Chunk(document_id=doc.id, chunk_index=0, text=doc.extracted_text)
db.add(chunk)
db.commit()
db.refresh(chunk)
print("Inserted chunk:", chunk)

fetched = db.query(Document).filter(Document.id == doc.id).one()
print("Fetched document has", len(fetched.chunks), "chunk(s)")
assert len(fetched.chunks) == 1
assert fetched.chunks[0].text == doc.extracted_text

# Clean up so re-running this script doesn't pile up rows.
db.delete(fetched)
db.commit()
db.close()

print("KV-7 schema check passed.")
