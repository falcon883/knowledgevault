"""
Give the documents from before accounts existed to a real account (KV-42).

    python claim_documents.py you@example.com

When the schema upgrade added accounts, every document that already existed was
given to a placeholder user that nobody can sign in as. Sign up for an account
first (POST /auth/signup, or the sign-up screen), then run this with that
account's email to move those documents over. It is safe to re-run.
"""

import sys

from sqlalchemy import select, update

from database import SessionLocal
from init_db import DEFAULT_USER_EMAIL
from models import Document, User


def main(email: str) -> int:
    email = email.strip().lower()
    with SessionLocal() as db:
        target = db.scalar(select(User).where(User.email == email))
        placeholder = db.scalar(select(User).where(User.email == DEFAULT_USER_EMAIL))
        if target is None:
            print(f"No account with the email {email}. Sign up first, then run this again.")
            return 1
        if placeholder is None:
            print("There are no documents from before accounts existed. Nothing to do.")
            return 0
        result = db.execute(
            update(Document).where(Document.user_id == placeholder.id).values(user_id=target.id)
        )
        db.commit()
        print(f"Moved {result.rowcount} document(s) to {email}.")
        return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
