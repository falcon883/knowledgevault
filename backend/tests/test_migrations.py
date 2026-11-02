"""
KV-36: database migrations (Alembic), including upgrading databases that were
made before Alembic or before accounts existed.

Each test works in its own scratch schema, so it never sees or changes the real
tables, whatever your own database contains. (The scratch schema's search path
also lists public, but only so the pgvector type can be found.)
"""

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

import settings
from database import Base
from init_db import DEFAULT_USER_EMAIL, alembic_config, current_revision, upgrade_schema
from uploads import content_hash

S = "kv_migrations_scratch"

PRE_ACCOUNTS_SCHEMA = [
    """CREATE TABLE documents (
        id SERIAL PRIMARY KEY,
        filename VARCHAR NOT NULL,
        content_type VARCHAR NOT NULL,
        size_bytes INTEGER NOT NULL,
        extracted_text TEXT,
        uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        {hash_column}
        tags TEXT,
        summary TEXT
    )""",
    "CREATE TABLE chunks ("
    " id SERIAL PRIMARY KEY,"
    " document_id INTEGER NOT NULL REFERENCES documents (id),"
    " chunk_index INTEGER NOT NULL,"
    " text TEXT NOT NULL,"
    " embedding vector(384))",
]

TWO_DOCUMENTS = (
    "INSERT INTO documents (filename, content_type, size_bytes, extracted_text) VALUES "
    "('old_one.txt', 'text/plain', 3, 'Legacy   notes on\nsourdough starters.'), "
    "('old_two.txt', 'text/plain', 0, NULL)"
)
A_CHUNK_PER_DOCUMENT = (
    "INSERT INTO chunks (document_id, chunk_index, text, embedding) "
    "SELECT id, 0, 'chunk of ' || filename, array_fill(0.5::real, ARRAY[384])::vector FROM documents"
)


@pytest.fixture
def scratch():
    """An engine on an empty scratch schema."""
    admin = create_engine(settings.DATABASE_URL)
    with admin.begin() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {S} CASCADE"))
        conn.execute(text(f"CREATE SCHEMA {S}"))
    engine = create_engine(settings.DATABASE_URL, connect_args={"options": f"-csearch_path={S},public"})
    yield engine
    engine.dispose()
    with admin.begin() as conn:
        conn.execute(text(f"DROP SCHEMA {S} CASCADE"))
    admin.dispose()


def run(engine, sql):
    with engine.begin() as conn:
        conn.execute(text(sql))


def scalar(engine, sql):
    with engine.connect() as conn:
        return conn.execute(text(sql)).scalar_one()


def column_names(engine, table):
    return {c["name"] for c in inspect(engine).get_columns(table, schema=S)}


def head() -> str:
    return ScriptDirectory.from_config(alembic_config()).get_current_head()


def make_pre_accounts_database(engine, with_hash=True):
    """The tables as Sprint 3 left them, holding two documents with a chunk each."""
    hash_column = "content_hash VARCHAR(64)," if with_hash else ""
    for statement in PRE_ACCOUNTS_SCHEMA:
        run(engine, statement.format(hash_column=hash_column))
    if with_hash:
        run(engine, "CREATE INDEX ix_documents_content_hash ON documents (content_hash)")
    run(engine, TWO_DOCUMENTS)
    run(engine, A_CHUNK_PER_DOCUMENT)


# --- the migrations themselves -------------------------------------------------


def test_there_is_a_single_line_of_migrations():
    assert len(ScriptDirectory.from_config(alembic_config()).get_heads()) == 1


def test_an_empty_database_is_built_from_scratch(scratch):
    assert current_revision(scratch) is None
    upgrade_schema(scratch)

    tables = set(inspect(scratch).get_table_names(schema=S))
    assert {"documents", "chunks", "users", "alembic_version"} <= tables
    assert current_revision(scratch) == head()


def test_the_migrations_build_exactly_what_the_models_describe(scratch):
    """If this fails, a model changed without a migration: run `alembic revision --autogenerate -m "..."`."""
    upgrade_schema(scratch)
    with scratch.begin() as conn:
        command.check(alembic_config(conn))  # raises if autogenerate would find any change


def test_running_it_again_changes_nothing(scratch):
    make_pre_accounts_database(scratch)
    upgrade_schema(scratch)
    before = (
        scalar(scratch, f"SELECT count(*) FROM {S}.users"),
        scalar(scratch, f"SELECT count(*) FROM {S}.documents"),
        current_revision(scratch),
    )
    upgrade_schema(scratch)
    after = (
        scalar(scratch, f"SELECT count(*) FROM {S}.users"),
        scalar(scratch, f"SELECT count(*) FROM {S}.documents"),
        current_revision(scratch),
    )
    assert after == before


def test_the_migrations_can_be_undone_and_redone(scratch):
    upgrade_schema(scratch)
    with scratch.begin() as conn:
        command.downgrade(alembic_config(conn), "base")
    assert set(inspect(scratch).get_table_names(schema=S)) == {"alembic_version"}
    assert current_revision(scratch) is None

    upgrade_schema(scratch)
    assert current_revision(scratch) == head()


# --- databases that already exist ---------------------------------------------


def test_a_database_made_before_alembic_keeps_all_its_data(scratch):
    """What the AWS server and every laptop look like: tables from the old init_db.py, no alembic_version."""
    Base.metadata.create_all(bind=scratch, checkfirst=False)
    run(scratch, "INSERT INTO users (email, password_hash, created_at) VALUES ('me@example.test', 'x', now())")
    run(
        scratch,
        "INSERT INTO documents (user_id, filename, content_type, size_bytes, extracted_text, uploaded_at, content_hash) "
        "SELECT id, 'mine.txt', 'text/plain', 3, 'abc', now(), 'h' FROM users",
    )
    run(scratch, A_CHUNK_PER_DOCUMENT)
    assert current_revision(scratch) is None

    upgrade_schema(scratch)

    assert current_revision(scratch) == head()
    assert scalar(scratch, f"SELECT count(*) FROM {S}.users") == 1, "no placeholder user: every document had an owner"
    assert scalar(scratch, f"SELECT filename FROM {S}.documents") == "mine.txt"
    assert scalar(scratch, f"SELECT content_hash FROM {S}.documents") == "h"
    assert scalar(scratch, f"SELECT count(*) FROM {S}.chunks") == 1
    assert scalar(scratch, f"SELECT embedding::text LIKE '[0.5,0.5,%' FROM {S}.chunks") is True


def test_a_database_from_before_accounts_keeps_its_documents_and_chunks(scratch):
    make_pre_accounts_database(scratch)
    upgrade_schema(scratch)

    assert scalar(scratch, f"SELECT count(*) FROM {S}.documents") == 2
    assert scalar(scratch, f"SELECT count(*) FROM {S}.chunks") == 2
    assert scalar(scratch, f"SELECT embedding::text LIKE '[0.5,0.5,%' FROM {S}.chunks LIMIT 1") is True

    default_id = scalar(scratch, f"SELECT id FROM {S}.users WHERE email = '{DEFAULT_USER_EMAIL}'")
    assert scalar(scratch, f"SELECT count(DISTINCT user_id) FROM {S}.documents") == 1
    assert scalar(scratch, f"SELECT min(user_id) FROM {S}.documents") == default_id
    assert not scalar(scratch, f"SELECT password_hash FROM {S}.users WHERE id = {default_id}").startswith("$2"), (
        "nobody can sign in as the default user"
    )

    user_id = next(c for c in inspect(scratch).get_columns("documents", schema=S) if c["name"] == "user_id")
    assert user_id["nullable"] is False, "user_id is required once everything has an owner"
    assert "ix_documents_user_id" in {i["name"] for i in inspect(scratch).get_indexes("documents", schema=S)}


def test_no_default_user_is_made_when_there_is_nothing_to_give(scratch):
    make_pre_accounts_database(scratch)
    run(scratch, "DELETE FROM chunks")
    run(scratch, "DELETE FROM documents")
    upgrade_schema(scratch)
    assert scalar(scratch, f"SELECT count(*) FROM {S}.users") == 0


def test_documents_from_before_the_hash_existed_are_backfilled(scratch):
    make_pre_accounts_database(scratch, with_hash=False)
    assert "content_hash" not in column_names(scratch, "documents")

    upgrade_schema(scratch)

    with scratch.connect() as conn:
        hashes = dict(conn.execute(text(f"SELECT filename, content_hash FROM {S}.documents")).all())
    assert hashes["old_one.txt"] == content_hash("Legacy notes on sourdough starters."), (
        "must match the hash the app computes, or the old document would never be seen as a duplicate"
    )
    assert hashes["old_two.txt"] is None, "a document with no text stays unhashed"
    assert "ix_documents_content_hash" in {i["name"] for i in inspect(scratch).get_indexes("documents", schema=S)}


def test_a_failed_upgrade_changes_nothing(scratch):
    make_pre_accounts_database(scratch)
    run(scratch, "CREATE TABLE users (id SERIAL PRIMARY KEY, email VARCHAR(254) NOT NULL UNIQUE)")  # wrong shape

    with pytest.raises(Exception):
        upgrade_schema(scratch)

    assert current_revision(scratch) is None, "nothing is recorded as applied"
    assert "user_id" not in column_names(scratch, "documents"), "the half-done change was rolled back"
    assert scalar(scratch, f"SELECT count(*) FROM {S}.documents") == 2


def test_claiming_moves_the_default_users_documents(scratch, monkeypatch):
    import claim_documents
    from sqlalchemy.orm import sessionmaker

    make_pre_accounts_database(scratch)
    upgrade_schema(scratch)
    run(scratch, "INSERT INTO users (email, password_hash, created_at) VALUES ('me@example.test', 'x', now())")
    monkeypatch.setattr(claim_documents, "SessionLocal", sessionmaker(bind=scratch))

    assert claim_documents.main("nobody@example.test") == 1, "needs an existing account"
    assert claim_documents.main("ME@example.test") == 0
    me = scalar(scratch, f"SELECT id FROM {S}.users WHERE email = 'me@example.test'")
    assert scalar(scratch, f"SELECT count(*) FROM {S}.documents WHERE user_id = {me}") == 2
    assert claim_documents.main("me@example.test") == 0, "safe to run again"
