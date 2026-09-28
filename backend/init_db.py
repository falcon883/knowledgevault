"""
Run this once to create the tables defined in models.py.

    python init_db.py

Safe to re-run - create_all only creates tables that don't already exist.
"""

from database import Base, engine
import models  # noqa: F401  (import registers the models with Base's metadata)

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("Tables created:", list(Base.metadata.tables.keys()))
