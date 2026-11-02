"""
Alembic environment (KV-36): tells Alembic which database to change and which
models describe it.

Two ways in, same result:
  - the command line (`alembic upgrade head`) connects with DATABASE_URL;
  - the app (init_db.upgrade_schema) hands over a connection it already opened.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import text

import models  # noqa: F401  (registers the tables with Base.metadata)
from database import Base, engine

config = context.config
target_metadata = Base.metadata


def include_object(obj, name, type_, reflected, compare_to) -> bool:
    # Alembic's own bookkeeping table is not one of our models; without this,
    # `alembic revision --autogenerate` would propose dropping it.
    return not (type_ == "table" and name == "alembic_version")


def _run(connection) -> None:
    # Keep alembic_version in the schema the tables live in, never in some other
    # schema that happens to be on the search path.
    schema = connection.execute(text("SELECT current_schema()")).scalar_one()
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table_schema=schema,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:  # called from the app: its transaction decides when to commit
        _run(connection)
        return
    if config.config_file_name:
        fileConfig(config.config_file_name, disable_existing_loggers=False)
    with engine.begin() as connection:  # all the migrations succeed together or not at all
        _run(connection)


if context.is_offline_mode():
    raise RuntimeError("KnowledgeVault migrations need a live database; --sql is not supported.")
run_migrations_online()
