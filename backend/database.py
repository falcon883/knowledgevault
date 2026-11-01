"""
KnowledgeVault backend - database connection setup.

The app uses Postgres because the `chunks.embedding` column uses pgvector
(see models.py), which is a Postgres extension and has no SQLite equivalent.
The connection URL comes from the DATABASE_URL setting (see settings.py); there
is no default, so no credentials are kept in the code. See backend/README.md.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from settings import DATABASE_URL

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a database session and closes it after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
