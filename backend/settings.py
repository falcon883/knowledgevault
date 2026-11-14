"""
KnowledgeVault backend - configuration (KV-37).

Every setting the app needs comes from an environment variable, so the same
code runs on a laptop, in Docker and on AWS without edits. For local work put
them in backend/.env (copy .env.example); real environment variables win over
the file.

    DATABASE_URL    required, no default (so no credentials live in the code)
    SECRET_KEY      required, no default: signs the sign-in tokens (KV-42);
                    at least 32 characters, e.g. `openssl rand -hex 32`
    ACCESS_TOKEN_HOURS  how long a sign-in lasts (default 24)
    CORS_ORIGINS    comma-separated browser origins allowed to call the API
                    (default: the local Vite dev server)
    MAX_UPLOAD_MB   largest upload accepted (default 10, read in uploads.py)

Sign-in limits (KV-54), all optional:

    LOGIN_MAX_FAILURES_PER_EMAIL  wrong passwords allowed per email (default 5)
    LOGIN_MAX_FAILURES_PER_IP     wrong passwords allowed per client address
                                  (default 20; higher because people share one)
    LOGIN_WINDOW_MINUTES          failures count for this long, and a lockout
                                  lasts at most this long (default 10)

Password reset (KV-53), all optional:

    FRONTEND_URL        where the app is served; reset links point here
                        (default: the first CORS_ORIGINS entry)
    RESET_TOKEN_MINUTES how long a reset link works (default 30)
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, MAIL_FROM
                        an outgoing mail server. Without SMTP_HOST no email is
                        sent and the reset link is written to the server log
                        instead (see mailer.py)

Tests only: TEST_DATABASE_URL, KV_FAKE_EMBEDDINGS, BCRYPT_ROUNDS (see
tests/conftest.py).
"""

import os

from dotenv import load_dotenv

load_dotenv()

DEFAULT_CORS_ORIGINS = "http://localhost:5173"
MIN_SECRET_KEY_LENGTH = 32


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


def validate_secret_key(value: str) -> str:
    """The token-signing key must be long enough that it cannot be guessed."""
    if len(value) < MIN_SECRET_KEY_LENGTH:
        raise ConfigError(
            f"SECRET_KEY is too short ({len(value)} characters). Use at least "
            f"{MIN_SECRET_KEY_LENGTH}, for example the output of: "
            'python -c "import secrets; print(secrets.token_hex(32))"'
        )
    return value


def int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    """A whole-number setting with a default, kept inside sensible limits."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        number = int(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a whole number, not {raw!r}.") from None
    if not minimum <= number <= maximum:
        raise ConfigError(f"{name} must be between {minimum} and {maximum}, not {number}.")
    return number


def parse_origins(raw: str | None) -> list[str]:
    """
    Turn "http://a.com, http://b.com/" into ["http://a.com", "http://b.com"].
    Blank entries are dropped, and a trailing slash is removed because browsers
    never send one in the Origin header.
    """
    origins = [part.strip().rstrip("/") for part in (raw or "").split(",")]
    return [origin for origin in origins if origin]


DATABASE_URL = require_env("DATABASE_URL")
SECRET_KEY = validate_secret_key(require_env("SECRET_KEY"))
ACCESS_TOKEN_HOURS = int_env("ACCESS_TOKEN_HOURS", default=24, minimum=1, maximum=24 * 30)
# Cost of hashing a password. 12 is a sound default; tests lower it to run fast.
BCRYPT_ROUNDS = int_env("BCRYPT_ROUNDS", default=12, minimum=4, maximum=16)

CORS_ORIGINS = parse_origins(os.getenv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS)) or parse_origins(
    DEFAULT_CORS_ORIGINS
)

# --- Password reset (KV-53) ---
FRONTEND_URL = os.getenv("FRONTEND_URL", "").strip().rstrip("/") or CORS_ORIGINS[0]
RESET_TOKEN_MINUTES = int_env("RESET_TOKEN_MINUTES", default=30, minimum=5, maximum=24 * 60)

SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int_env("SMTP_PORT", default=587, minimum=1, maximum=65535)
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
MAIL_FROM = os.getenv("MAIL_FROM", "").strip() or SMTP_USER

# --- Limits on failed sign-ins (KV-54) ---
LOGIN_MAX_FAILURES_PER_EMAIL = int_env("LOGIN_MAX_FAILURES_PER_EMAIL", default=5, minimum=1, maximum=1000)
LOGIN_MAX_FAILURES_PER_IP = int_env("LOGIN_MAX_FAILURES_PER_IP", default=20, minimum=1, maximum=10000)
LOGIN_WINDOW_MINUTES = int_env("LOGIN_WINDOW_MINUTES", default=10, minimum=1, maximum=24 * 60)
