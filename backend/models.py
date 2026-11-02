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

# Stored as the password hash of the "default" user that the schema upgrade
# creates to own documents from before accounts existed. It is not a valid
# bcrypt hash, so nobody can sign in as that user.
UNUSABLE_PASSWORD = "!"


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    """An account (KV-42). Documents belong to exactly one user."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(254), nullable=False, unique=True, index=True)  # stored lowercase
    password_hash = Column(String, nullable=False)  # bcrypt, never the password itself
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    documents = relationship("Document", back_populates="owner")

    def __repr__(self):
        return f"<User id={self.id} email={self.email!r}>"


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)

    # KV-42: whose document this is. Every query in main.py filters on it, so
    # one user never sees or searches another user's documents.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    extracted_text = Column(Text, nullable=True)
    uploaded_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    # KV-25: fingerprint of the extracted text (see uploads.content_hash), used
    # to spot a file that was already uploaded. Null only for rows not yet
    # backfilled by migration 0001.
    content_hash = Column(String(64), nullable=True, index=True)

    # Auto-tagging/summarization results (KV-21) land here once built.
    tags = Column(Text, nullable=True)  # comma-separated for now; revisit if needed
    summary = Column(Text, nullable=True)

    owner = relationship("User", back_populates="documents")
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
