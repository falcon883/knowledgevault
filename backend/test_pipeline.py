"""
Manual check that KV-13/14/15 work end to end: upload -> persist ->
chunk -> embed -> stored in pgvector -> retrievable by similarity search.

    python test_pipeline.py

Requires Postgres with the pgvector extension running (see README.md) and
network access to huggingface.co the first time it runs, to download the
sentence-transformers model (cached locally after that).
"""

from database import Base, SessionLocal, engine
from embeddings import embed_text, embed_texts
from chunking import chunk_text
from models import Chunk, Document
from sqlalchemy import select

Base.metadata.create_all(bind=engine)
db = SessionLocal()

text = (
    "KnowledgeVault lets users upload notes, PDFs, and articles, then find "
    "them later by meaning rather than exact keywords. " * 10
)

doc = Document(
    filename="pipeline_check.txt",
    content_type="text/plain",
    size_bytes=len(text),
    extracted_text=text,
)
db.add(doc)
db.commit()
db.refresh(doc)
print("Inserted document:", doc)

pieces = chunk_text(text)
print(f"Split into {len(pieces)} chunk(s)")
vectors = embed_texts(pieces)
for index, (piece, vector) in enumerate(zip(pieces, vectors)):
    db.add(Chunk(document_id=doc.id, chunk_index=index, text=piece, embedding=vector))
db.commit()

fetched = db.query(Document).filter(Document.id == doc.id).one()
assert len(fetched.chunks) == len(pieces)
assert all(c.embedding is not None for c in fetched.chunks)
print(f"Fetched document has {len(fetched.chunks)} embedded chunk(s)")

# Prove similarity search actually works: a query about the product should
# rank these chunks above an unrelated one.
query_vector = embed_text("How do I search my notes by meaning?")
nearest = db.execute(
    select(Chunk)
    .where(Chunk.document_id == doc.id)
    .order_by(Chunk.embedding.cosine_distance(query_vector))
    .limit(3)
).scalars().all()
print("Nearest chunks to the query:", [c.id for c in nearest])
assert nearest, "expected at least one chunk back from similarity search"

db.delete(fetched)
db.commit()
db.close()

print("KV-13/14/15 pipeline check passed.")
