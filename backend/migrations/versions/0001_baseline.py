"""baseline: documents and chunks, as they were before accounts

Revision ID: 0001
Revises:
Create Date: 2026-11-01

Everything the app had through Sprint 3: the pgvector extension, the documents
table (with content_hash, tags and summary) and the chunks table.

This is also where databases created by the old init_db.py (before Alembic
existed) join the history. Every step first checks whether the table or column
is already there, so on such a database this migration changes nothing except
filling in content_hash for old rows, and on an empty one it builds the lot.
Later migrations are ordinary and need no such checks.

Never import app code here: a migration must keep meaning what it meant on the
day it was written, even after models.py changes.
"""

import hashlib

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

EMBEDDING_DIM = 384  # all-MiniLM-L6-v2


def _schema(bind) -> str:
    return bind.execute(sa.text("SELECT current_schema()")).scalar_one()


def _content_hash(text: str) -> str:
    # A frozen copy of uploads.content_hash as it was when this migration was written.
    return hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest()


def upgrade() -> None:
    bind = op.get_bind()
    schema = _schema(bind)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    if not sa.inspect(bind).has_table("documents", schema=schema):
        op.create_table(
            "documents",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("filename", sa.String(), nullable=False),
            sa.Column("content_type", sa.String(), nullable=False),
            sa.Column("size_bytes", sa.Integer(), nullable=False),
            sa.Column("extracted_text", sa.Text(), nullable=True),
            sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("content_hash", sa.String(length=64), nullable=True),
            sa.Column("tags", sa.Text(), nullable=True),
            sa.Column("summary", sa.Text(), nullable=True),
        )
        op.create_index("ix_documents_id", "documents", ["id"])
        op.create_index("ix_documents_content_hash", "documents", ["content_hash"])
    else:
        inspector = sa.inspect(bind)
        columns = {c["name"] for c in inspector.get_columns("documents", schema=schema)}
        indexes = {i["name"] for i in inspector.get_indexes("documents", schema=schema)}
        if "content_hash" not in columns:
            op.add_column("documents", sa.Column("content_hash", sa.String(length=64), nullable=True))
        if "ix_documents_content_hash" not in indexes:
            op.create_index("ix_documents_content_hash", "documents", ["content_hash"])
        if "tags" not in columns:
            op.add_column("documents", sa.Column("tags", sa.Text(), nullable=True))
        if "summary" not in columns:
            op.add_column("documents", sa.Column("summary", sa.Text(), nullable=True))

    if not sa.inspect(bind).has_table("chunks", schema=schema):
        op.create_table(
            "chunks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id"), nullable=False),
            sa.Column("chunk_index", sa.Integer(), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        )
        op.create_index("ix_chunks_id", "chunks", ["id"])

    # Documents uploaded before duplicate detection (KV-25) have no hash yet, so
    # they could never be recognised as a re-upload. Documents with no text stay empty.
    rows = bind.execute(
        sa.text("SELECT id, extracted_text FROM documents WHERE content_hash IS NULL")
    ).all()
    for doc_id, extracted in rows:
        if (extracted or "").strip():
            bind.execute(
                sa.text("UPDATE documents SET content_hash = :h WHERE id = :id"),
                {"h": _content_hash(extracted), "id": doc_id},
            )


def downgrade() -> None:
    # Destroys every document and chunk. Only for throwaway databases.
    op.drop_table("chunks")
    op.drop_table("documents")
