"""accounts: users table and per-user documents (KV-42)

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-01

Adds the users table and documents.user_id. Documents that already exist are
given to a placeholder "default" user that nobody can sign in as (it is created
only when there is something to give); `python claim_documents.py <email>` moves
them to a real account later. Then user_id becomes required.

Like the baseline, each step checks first, so a database that already has
accounts (made by the old init_db.py) passes through unchanged.
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

DEFAULT_USER_EMAIL = "default@knowledgevault.local"
UNUSABLE_PASSWORD = "!"  # not a valid bcrypt hash, so no password can match it


def _schema(bind) -> str:
    return bind.execute(sa.text("SELECT current_schema()")).scalar_one()


def upgrade() -> None:
    bind = op.get_bind()
    schema = _schema(bind)

    if not sa.inspect(bind).has_table("users", schema=schema):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("email", sa.String(length=254), nullable=False),
            sa.Column("password_hash", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_users_id", "users", ["id"])
        op.create_index("ix_users_email", "users", ["email"], unique=True)

    inspector = sa.inspect(bind)
    if "user_id" not in {c["name"] for c in inspector.get_columns("documents", schema=schema)}:
        op.add_column("documents", sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True))
    if "ix_documents_user_id" not in {i["name"] for i in inspector.get_indexes("documents", schema=schema)}:
        op.create_index("ix_documents_user_id", "documents", ["user_id"])

    orphans = bind.execute(sa.text("SELECT count(*) FROM documents WHERE user_id IS NULL")).scalar_one()
    if orphans:
        bind.execute(
            sa.text(
                "INSERT INTO users (email, password_hash, created_at) "
                "VALUES (:email, :hash, now()) ON CONFLICT (email) DO NOTHING"
            ),
            {"email": DEFAULT_USER_EMAIL, "hash": UNUSABLE_PASSWORD},
        )
        default_id = bind.execute(
            sa.text("SELECT id FROM users WHERE email = :email"), {"email": DEFAULT_USER_EMAIL}
        ).scalar_one()
        bind.execute(sa.text("UPDATE documents SET user_id = :id WHERE user_id IS NULL"), {"id": default_id})

    column = next(c for c in sa.inspect(bind).get_columns("documents", schema=schema) if c["name"] == "user_id")
    if column["nullable"]:
        op.alter_column("documents", "user_id", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    # Documents stay, but who owned them is forgotten, and so are all accounts.
    op.drop_index("ix_documents_user_id", table_name="documents")
    op.drop_column("documents", "user_id")
    op.drop_table("users")
