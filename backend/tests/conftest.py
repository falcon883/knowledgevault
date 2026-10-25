"""
Shared setup for the backend tests (KV-27).

    pytest                          # from the backend/ folder

Needs Postgres with pgvector running (see README.md). By default the tests
use the same database as the app (DATABASE_URL) and delete every document they
create, so they don't touch yours. To keep them completely apart, point
TEST_DATABASE_URL at a separate empty database and it is used instead.

The real embedding model is used by default (the first run downloads it).
Set KV_FAKE_EMBEDDINGS=1 for a quick run with a stand-in that needs no
download; search ranking is then rougher but every check still passes.
"""

import hashlib
import os
import re

# Must happen before the app modules are imported: database.py reads this once.
if os.getenv("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

import embeddings  # noqa: E402
import main  # noqa: E402
import uploads  # noqa: E402
from database import Base, SessionLocal, engine  # noqa: E402
from init_db import upgrade_schema  # noqa: E402
from models import Document  # noqa: E402

if os.getenv("KV_FAKE_EMBEDDINGS") == "1":
    _WORD = re.compile(r"[a-z]{3,}")

    def _fake_vector(value: str) -> list[float]:
        v = np.zeros(384)
        for word in _WORD.findall(value.lower()):
            v[int(hashlib.md5(word.encode()).hexdigest(), 16) % 384] += 1.0
        norm = np.linalg.norm(v)
        if norm == 0:
            v[0], norm = 1.0, 1.0
        return (v / norm).tolist()

    embeddings._encode = lambda texts: [_fake_vector(t) for t in texts]


@pytest.fixture(scope="session", autouse=True)
def database():
    """Make sure pgvector, the tables and the latest columns exist."""
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    except Exception:
        pass  # already installed, and this user may not be allowed to run it
    Base.metadata.create_all(bind=engine)
    upgrade_schema()


@pytest.fixture(autouse=True)
def clean_documents():
    """After every test, delete any documents (and their chunks) it created."""
    with SessionLocal() as db:
        before = set(db.scalars(select(Document.id)))
    yield
    with SessionLocal() as db:
        for doc in db.scalars(select(Document)):
            if doc.id not in before:
                db.delete(doc)
        db.commit()


@pytest.fixture
def client():
    return TestClient(main.app)


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def upload(client):
    """upload(name, data, content_type="text/plain", **query_params) -> response"""

    def _upload(name, data, content_type="text/plain", **params):
        return client.post(
            "/upload", files={"file": (name, data, content_type)}, params=params
        )

    return _upload


@pytest.fixture
def small_limit(monkeypatch):
    """A 2 KB upload limit, so the 'too large' cases don't need a big file."""
    megabytes = 0.002
    limit = int(megabytes * 1024 * 1024)
    monkeypatch.setattr(uploads, "MAX_UPLOAD_MB", megabytes)
    monkeypatch.setattr(uploads, "MAX_UPLOAD_BYTES", limit)
    monkeypatch.setattr(main, "MAX_UPLOAD_MB", megabytes)
    monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", limit)
    return limit
