"""
KnowledgeVault backend - configuration (KV-37).

Every setting the app needs comes from an environment variable, so the same
code runs on a laptop, in Docker and on AWS without edits. For local work put
them in backend/.env (copy .env.example); real environment variables win over
the file.

    DATABASE_URL    required, no default (so no credentials live in the code)
    CORS_ORIGINS    comma-separated browser origins allowed to call the API
                    (default: the local Vite dev server)
    MAX_UPLOAD_MB   largest upload accepted (default 10, read in uploads.py)

Tests only: TEST_DATABASE_URL, KV_FAKE_EMBEDDINGS (see tests/conftest.py).
"""

import os

from dotenv import load_dotenv

load_dotenv()

DEFAULT_CORS_ORIGINS = "http://localhost:5173"


class ConfigError(RuntimeError):
    """A required setting is missing or unusable."""


def require_env(name: str) -> str:
    """Return a setting that has no default, or explain how to set it."""
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(
            f"{name} is not set. Copy backend/.env.example to backend/.env and "
            f"fill it in, or set {name} in the environment (see backend/README.md)."
        )
    return value


def parse_origins(raw: str | None) -> list[str]:
    """
    Turn "http://a.com, http://b.com/" into ["http://a.com", "http://b.com"].
    Blank entries are dropped, and a trailing slash is removed because browsers
    never send one in the Origin header.
    """
    origins = [part.strip().rstrip("/") for part in (raw or "").split(",")]
    return [origin for origin in origins if origin]


DATABASE_URL = require_env("DATABASE_URL")

CORS_ORIGINS = parse_origins(os.getenv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS)) or parse_origins(
    DEFAULT_CORS_ORIGINS
)
