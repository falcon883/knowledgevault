"""
Run this once to enable pgvector and create the tables defined in
models.py.

    python init_db.py

Safe to re-run - CREATE EXTENSION IF NOT EXISTS and create_all only create
what doesn't already exist.
"""

from sqlalchemy import text

from database import Base, engine
import models  # noqa: F401  (import registers the models with Base's metadata)

if __name__ == "__main__":
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    Base.metadata.create_all(bind=engine)
    print("Tables created:", list(Base.metadata.tables.keys()))
