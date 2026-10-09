"""
KnowledgeVault backend - database connection setup.

Sprint 2 switches the default from SQLite to Postgres, because the
`chunks.embedding` column now uses pgvector (see models.py), which is a
Postgres extension and has no SQLite equivalent. Point DATABASE_URL at
your own local Postgres instance; see backend/README.md for setup.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://knowledgevault:knowledgevault@localhost:5432/knowledgevault",
)

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
