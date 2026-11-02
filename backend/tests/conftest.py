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
import itertools
import os
import re
import uuid

# Must happen before the app modules are imported: database.py reads this once.
if os.getenv("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]

# KV-42: the app will not start without a signing key. Tests get a throwaway
# one, and cheap password hashing so the many sign-ups stay fast.
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-0123456789abcdef0123456789abcdef")
os.environ.setdefault("BCRYPT_ROUNDS", "4")

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

import embeddings  # noqa: E402
import main  # noqa: E402
import uploads  # noqa: E402
from database import SessionLocal  # noqa: E402
from init_db import upgrade_schema  # noqa: E402
from models import Document, User  # noqa: E402

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
    """Bring the test database up to date with the migrations (KV-36)."""
    upgrade_schema()


@pytest.fixture(autouse=True)
def clean_documents():
    """After every test, delete any documents (and their chunks) and users it created."""
    with SessionLocal() as db:
        documents_before = set(db.scalars(select(Document.id)))
        users_before = set(db.scalars(select(User.id)))
    yield
    with SessionLocal() as db:
        for doc in db.scalars(select(Document)):
            if doc.id not in documents_before:
                db.delete(doc)
        db.commit()  # documents first: they point at their owners
        for user in db.scalars(select(User)):
            if user.id not in users_before:
                db.delete(user)
        db.commit()


PASSWORD = "correct horse battery"
_user_counter = itertools.count(1)


def signed_in_client(email: str | None = None) -> TestClient:
    """
    A TestClient already signed in as a brand new user. `.user_id` and `.email`
    say who it is. Every call it makes carries that user's token.
    """
    email = email or f"user{next(_user_counter)}-{uuid.uuid4().hex[:8]}@example.test"
    client = TestClient(main.app)
    response = client.post("/auth/signup", json={"email": email, "password": PASSWORD})
    assert response.status_code == 201, response.text
    body = response.json()
    client.headers["Authorization"] = f"Bearer {body['access_token']}"
    client.user_id = body["user"]["id"]
    client.email = email
    return client


@pytest.fixture
def client():
    """Signed in as a fresh user, so existing tests need no changes to their requests."""
    return signed_in_client()


@pytest.fixture
def other_client():
    """A second signed-in user, for checking that users cannot see each other's data."""
    return signed_in_client()


@pytest.fixture
def anonymous_client():
    """No token at all."""
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
