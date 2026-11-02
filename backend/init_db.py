"""
Bring the database up to date (KV-36).

    python init_db.py

Runs every Alembic migration that has not been applied yet (enabling pgvector
and creating the tables on an empty database), so it is safe to run as often as
you like. It is the same as `alembic upgrade head`; see backend/README.md,
"Database migrations", for adding a migration when a model changes.

Databases made before Alembic existed need nothing special: the first run finds
the tables already there, keeps all their data, and records where they are.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import text

from database import engine

BACKEND_DIR = Path(__file__).resolve().parent

# Owns documents uploaded before accounts existed (KV-42). Nobody can sign in
# as this user; claim_documents.py moves its documents to a real account.
DEFAULT_USER_EMAIL = "default@knowledgevault.local"


def alembic_config(connection=None) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    if connection is not None:
        config.attributes["connection"] = connection
    return config


def upgrade_schema(bind=engine) -> None:
    """
    Apply every pending migration, all in one transaction: if one fails nothing
    is changed. Used by this script and when the API starts, so pulling new code
    never leaves the app running against an old schema.
    """
    with bind.begin() as connection:
        command.upgrade(alembic_config(connection), "head")


def current_revision(bind=engine) -> str | None:
    """The migration the database is at, or None if none has been applied."""
    with bind.connect() as connection:
        schema = connection.execute(text("SELECT current_schema()")).scalar_one()
        context = MigrationContext.configure(connection, opts={"version_table_schema": schema})
        return context.get_current_revision()


if __name__ == "__main__":
    before = current_revision()
    upgrade_schema()
    after = current_revision()
    if before == after:
        print(f"Database is up to date (migration {after}).")
    else:
        print(f"Database upgraded from {before or 'nothing'} to migration {after}.")
