"""
KnowledgeVault backend - database connection setup.

Defaults to a local SQLite file so both of you can run this without
installing Postgres. Set the DATABASE_URL environment variable to point
at real Postgres once AWS deployment (Theme 4) is set up - the models in
models.py work unchanged either way since they're plain SQLAlchemy.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./knowledgevault.db")

# check_same_thread is only needed for SQLite; harmless to set generally.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a database session and closes it after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
