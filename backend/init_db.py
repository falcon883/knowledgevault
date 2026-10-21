"""
Run this once to enable pgvector and create the tables defined in
models.py, and again after pulling a change that adds columns.

    python init_db.py

Safe to re-run - CREATE EXTENSION IF NOT EXISTS and create_all only create
what doesn't already exist, and upgrade_schema() only adds what is missing.
"""

from sqlalchemy import inspect, text

from database import Base, engine
import models  # noqa: F401  (import registers the models with Base's metadata)
from uploads import content_hash


def upgrade_schema(bind=engine) -> int:
    """
    Bring an existing database up to date. create_all makes missing tables
    but never changes one that exists, so new columns are added here.
    Returns how many documents were backfilled.

    KV-25: documents.content_hash (plus an index), filled in for documents
    uploaded before it existed so they count in duplicate detection too.
    """
    # Only run the ALTER / CREATE INDEX when something is actually missing:
    # they take a table lock, which a normal start-up should never wait for.
    inspector = inspect(bind)
    has_column = any(c["name"] == "content_hash" for c in inspector.get_columns("documents"))
    has_index = any(i["name"] == "ix_documents_content_hash" for i in inspector.get_indexes("documents"))
    with bind.begin() as conn:
        if not has_column:
            conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64)"))
        if not has_index:
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_documents_content_hash ON documents (content_hash)")
            )

    filled = 0
    with bind.begin() as conn:
        rows = conn.execute(
            text("SELECT id, extracted_text FROM documents WHERE content_hash IS NULL")
        ).all()
        for doc_id, extracted in rows:
            if not (extracted or "").strip():
                continue  # nothing to fingerprint
            conn.execute(
                text("UPDATE documents SET content_hash = :h WHERE id = :id"),
                {"h": content_hash(extracted), "id": doc_id},
            )
            filled += 1
    return filled


if __name__ == "__main__":
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    Base.metadata.create_all(bind=engine)
    filled = upgrade_schema()
    print("Tables created:", list(Base.metadata.tables.keys()))
    if filled:
        print(f"Backfilled content_hash for {filled} existing document(s).")
