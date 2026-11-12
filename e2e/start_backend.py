"""
Starts the API for the end-to-end tests (KV-32). Playwright runs this for you
(see playwright.config.js); you do not normally start it by hand.

    python e2e/start_backend.py        # from the repository root

What it does differently from a normal start:

  * It uses its own schema, kv_e2e, inside the usual database, and wipes that
    schema on every start. Your own documents and accounts are never touched,
    and you do not need a second database.
  * It listens on port 8100, not 8000, so it can run next to your dev server.
  * It uses a stand-in for the embedding model (the same idea as
    KV_FAKE_EMBEDDINGS in the backend tests), so there is no model to download
    and uploads are fast. Set E2E_REAL_EMBEDDINGS=1 to use the real model.
  * Passwords are hashed cheaply, so signing up takes milliseconds.

Settings it reads (all optional):
    E2E_DATABASE_URL    default: DATABASE_URL (environment or backend/.env, the
                        same place the API looks), else a Postgres on localhost:5432
    E2E_API_PORT        default 8100
    E2E_WEB_ORIGIN      the browser origin allowed to call the API
                        (default http://127.0.0.1:4173)
    E2E_REAL_EMBEDDINGS set to 1 to load the real sentence-transformers model
"""

import hashlib
import os
import re
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"

SCHEMA = "kv_e2e"
DEFAULT_DATABASE_URL = "postgresql+psycopg2://knowledgevault:knowledgevault@localhost:5432/knowledgevault"
HOST = "127.0.0.1"
PORT = int(os.getenv("E2E_API_PORT", "8100"))
WEB_ORIGIN = os.getenv("E2E_WEB_ORIGIN", "http://127.0.0.1:4173")


def prepare_database(url: str) -> str:
    """Empty the kv_e2e schema and return a URL whose connections use it."""
    base = make_url(url)
    admin = create_engine(base)
    with admin.begin() as conn:
        # pgvector lives in the usual place (public), not inside the schema we are about to drop.
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
        conn.execute(text(f"CREATE SCHEMA {SCHEMA}"))
    admin.dispose()
    # public stays on the path so the vector type can be found.
    return base.update_query_dict({"options": f"-csearch_path={SCHEMA},public"}).render_as_string(hide_password=False)


def use_stand_in_embeddings() -> None:
    """Word-hash vectors instead of the real model: texts that share words are close."""
    import numpy as np

    import embeddings

    word = re.compile(r"[a-z]{3,}")

    def vector(value: str) -> list[float]:
        v = np.zeros(384)
        for w in word.findall(value.lower()):
            v[int(hashlib.md5(w.encode()).hexdigest(), 16) % 384] += 1.0
        norm = np.linalg.norm(v)
        if norm == 0:
            v[0], norm = 1.0, 1.0
        return (v / norm).tolist()

    embeddings._encode = lambda texts: [vector(t) for t in texts]


def main() -> None:
    from dotenv import load_dotenv

    load_dotenv(BACKEND / ".env")  # real environment variables still win
    database_url = os.getenv("E2E_DATABASE_URL") or os.getenv("DATABASE_URL") or DEFAULT_DATABASE_URL
    os.environ["DATABASE_URL"] = prepare_database(database_url)
    os.environ["CORS_ORIGINS"] = WEB_ORIGIN
    os.environ["BCRYPT_ROUNDS"] = "4"
    os.environ.setdefault("SECRET_KEY", "e2e-only-secret-key-0123456789abcdef0123456789abcdef")

    sys.path.insert(0, str(BACKEND))
    if os.getenv("E2E_REAL_EMBEDDINGS") != "1":
        use_stand_in_embeddings()

    import uvicorn

    import main as app_module  # imported late: it reads the settings above

    print(f"E2E API on http://{HOST}:{PORT}  (schema {SCHEMA})", flush=True)
    uvicorn.run(app_module.app, host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
