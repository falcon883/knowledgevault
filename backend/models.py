"""
KnowledgeVault backend - data model.

Sprint 1 (KV-7) defined Document and Chunk with a placeholder embedding
column. Sprint 2 (KV-15) replaces that placeholder with a real pgvector
column now that the vector database choice is finalized: pgvector
(a Postgres extension) rather than a separate managed vector service,
since the team already runs Postgres for metadata and this avoids
standing up and paying for a second system.

EMBEDDING_DIM matches the output size of the chosen embedding model
(sentence-transformers/all-MiniLM-L6-v2, see embeddings.py) - 384.
"""

from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database import Base

EMBEDDING_DIM = 384


def utcnow():
    return datetime.now(timezone.utc)


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    extracted_text = Column(Text, nullable=True)
    uploaded_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    # KV-25: fingerprint of the extracted text (see uploads.content_hash), used
    # to spot a file that was already uploaded. Null only for rows not yet
    # backfilled by init_db.upgrade_schema().
    content_hash = Column(String(64), nullable=True, index=True)

    # Auto-tagging/summarization results (KV-21) land here once built.
    tags = Column(Text, nullable=True)  # comma-separated for now; revisit if needed
    summary = Column(Text, nullable=True)

    chunks = relationship(
        "Chunk", back_populates="document", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Document id={self.id} filename={self.filename!r}>"


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)  # order within the document
    text = Column(Text, nullable=False)

    # Real embedding vector (KV-15), generated from `text` at ingest time.
    embedding = Column(Vector(EMBEDDING_DIM), nullable=True)

    document = relationship("Document", back_populates="chunks")

    def __repr__(self):
        return f"<Chunk id={self.id} document_id={self.document_id} index={self.chunk_index}>"
