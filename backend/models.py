"""
KnowledgeVault backend - KV-7: initial data model.

Two tables for now, matching Section 5.1 / Roadmap Theme 1:

- Document: one row per uploaded file (metadata + full extracted text).
- Chunk: one row per text chunk of a document, the unit that will later
  get an embedding for semantic search (Roadmap Theme 2). The embedding
  column is a placeholder (nullable JSON/text) until the vector database
  choice is finalized and wired in.

A per-user "owner" column is deliberately left out of this first pass -
authentication and per-user data isolation are Roadmap Theme 4 work, and
adding it now would just mean re-migrating this schema later.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database import Base


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

    # Auto-tagging/summarization results (Roadmap Theme 2) land here once built.
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

    # Placeholder for the embedding vector once Theme 2 picks a vector DB
    # and embedding model. Stored as text (e.g. JSON-encoded) for now so
    # this schema doesn't block on that decision.
    embedding = Column(Text, nullable=True)

    document = relationship("Document", back_populates="chunks")

    def __repr__(self):
        return f"<Chunk id={self.id} document_id={self.document_id} index={self.chunk_index}>"
