"""
KnowledgeVault backend - accounts and sign-in (KV-42).

    POST /auth/signup   create an account, returns a token
    POST /auth/login    check email and password, returns a token
    GET  /auth/me       who the token belongs to
    POST /auth/forgot-password  email a link for choosing a new password (KV-53)
    POST /auth/reset-password   set a new password with the token from that link

A token is sent with every other request as `Authorization: Bearer <token>`.
Passwords are stored only as bcrypt hashes. Tokens are signed with SECRET_KEY
(HS256 JWT) and expire after ACCESS_TOKEN_HOURS.

Every problem comes back as {"detail": <message>, "code": <code>}, like upload
errors do:

    401  not_authenticated    no token was sent
    401  invalid_token        the token is damaged, forged, or its user is gone
    401  token_expired        the token is old; sign in again
    401  invalid_credentials  wrong email or password (the same answer for
                              both, so it does not reveal which emails exist)
    409  email_taken          signup with an email that already has an account
    422  invalid_email, weak_password, password_too_long
    400  invalid_reset_token  the reset token was never issued, or is damaged
    400  reset_token_expired  the reset link is older than RESET_TOKEN_MINUTES
    400  reset_token_used     the reset link was already used, or a newer one replaced it
"""

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from functools import cache

import bcrypt
import jwt
from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from mailer import send_email
from models import PasswordResetToken, User, utcnow
from settings import (
    ACCESS_TOKEN_HOURS,
    BCRYPT_ROUNDS,
    FRONTEND_URL,
    RESET_TOKEN_MINUTES,
    SECRET_KEY,
)

ALGORITHM = "HS256"
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_BYTES = 72  # bcrypt only reads the first 72 bytes
MAX_EMAIL_LENGTH = 254
RESERVED_EMAIL_DOMAIN = "knowledgevault.local"  # used by the default user (init_db.py)

EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")

# KV-53: one reset email per account per minute, so the form cannot be used to
# fill someone's inbox. Requests inside the minute get the usual answer and
# send nothing.
RESET_COOLDOWN_SECONDS = 60


class AuthError(Exception):
    """A sign-in or signup problem, answered as {"detail", "code"} (see main.py)."""

    def __init__(self, status_code: int, code: str, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.code = code
        self.detail = detail

    @property
    def headers(self) -> dict[str, str]:
        return {"WWW-Authenticate": "Bearer"} if self.status_code == 401 else {}


# --- passwords -----------------------------------------------------------------


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    """True if `password` matches the stored hash. Never raises."""
    if not password_hash.startswith("$2"):  # e.g. the default user's unusable password
        return False
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


@cache
def _dummy_hash() -> str:
    return hash_password("not-a-real-password")


def clean_email(raw: str) -> str:
    email = raw.strip().lower()
    if (
        len(email) > MAX_EMAIL_LENGTH
        or not EMAIL_PATTERN.fullmatch(email)
        or email.endswith("@" + RESERVED_EMAIL_DOMAIN)
    ):
        raise AuthError(422, "invalid_email", "Enter a valid email address.")
    return email


def check_new_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise AuthError(
            422, "weak_password", f"Use a password of at least {MIN_PASSWORD_LENGTH} characters."
        )
    if len(password.encode()) > MAX_PASSWORD_BYTES:
        raise AuthError(
            422, "password_too_long", f"Use a password of at most {MAX_PASSWORD_BYTES} bytes."
        )


# --- tokens --------------------------------------------------------------------


def create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(hours=ACCESS_TOKEN_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


bearer_scheme = HTTPBearer(
    auto_error=False,  # a missing token is answered by us, with a code
    description="The token from /auth/login or /auth/signup.",
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Dependency for every route that needs a signed-in user."""
    if credentials is None:
        raise AuthError(
            401,
            "not_authenticated",
            "Sign in to use KnowledgeVault. Send your token as 'Authorization: Bearer <token>'.",
        )
    try:
        payload = jwt.decode(
            credentials.credentials,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
        user_id = int(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise AuthError(401, "token_expired", "Your session has expired. Sign in again.") from None
    except (jwt.InvalidTokenError, ValueError):
        raise AuthError(401, "invalid_token", "That sign-in token is not valid. Sign in again.") from None

    user = db.get(User, user_id)
    if user is None:
        raise AuthError(401, "invalid_token", "That sign-in token is not valid. Sign in again.")
    return user


# --- routes --------------------------------------------------------------------

router = APIRouter(prefix="/auth", tags=["auth"])


class Credentials(BaseModel):
    email: str = Field(..., max_length=1000, examples=["you@example.com"])
    password: str = Field(..., max_length=1000)


def token_response(user: User) -> dict:
    return {
        "access_token": create_access_token(user.id),
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email},
    }


@router.post("/signup", status_code=201)
def signup(body: Credentials, db: Session = Depends(get_db)):
    """
    Create an account and sign in. The email is stored in lowercase and must be
    new; the password needs 8 to 72 characters. Returns the same body as login.
    """
    email = clean_email(body.email)
    check_new_password(body.password)

    taken = AuthError(409, "email_taken", "An account with this email already exists. Sign in instead.")
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise taken

    user = User(email=email, password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # two signups for one email at the same moment
        db.rollback()
        raise taken from None
    db.refresh(user)
    return token_response(user)


@router.post("/login")
def login(body: Credentials, db: Session = Depends(get_db)):
    """Sign in with email and password. Returns {access_token, token_type, user}."""
    wrong = AuthError(401, "invalid_credentials", "Wrong email or password.")
    user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    if user is None:
        verify_password(body.password, _dummy_hash())  # take as long as a real check
        raise wrong
    if not verify_password(body.password, user.password_hash):
        raise wrong
    return token_response(user)


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    """The signed-in user. Handy for the frontend to check a stored token."""
    return {"id": user.id, "email": user.email}


# --- password reset (KV-53) ------------------------------------------------------


def hash_reset_token(token: str) -> str:
    """What is stored for a reset token. A fast hash is fine: the token is 256 random bits."""
    return hashlib.sha256(token.encode()).hexdigest()


def reset_link(token: str) -> str:
    # The token goes in the query string of the app's home page, so the link
    # works on a static host with no special routing for a /reset-password page.
    return f"{FRONTEND_URL}/?reset_token={token}"


def send_reset_email(email: str, token: str) -> None:
    send_email(
        email,
        "Reset your KnowledgeVault password",
        "Someone asked to reset the password for this KnowledgeVault account.\n\n"
        f"To choose a new password, open this link within {RESET_TOKEN_MINUTES} minutes:\n\n"
        f"{reset_link(token)}\n\n"
        "If that was not you, ignore this email. Your password stays the same.\n",
    )


class ForgotPassword(BaseModel):
    email: str = Field(..., max_length=1000, examples=["you@example.com"])


class ResetPassword(BaseModel):
    token: str = Field(..., max_length=1000, description="The token from the link in the email.")
    password: str = Field(..., max_length=1000)


@router.post("/forgot-password", status_code=202)
def forgot_password(body: ForgotPassword, background: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Email a link for choosing a new password. The answer is always the same,
    whether or not the address has an account, so this cannot be used to find
    out who has one. The email is sent after the answer, so it takes the same
    time either way. Asking again invalidates the previous link.
    """
    email = clean_email(body.email)
    user = db.scalar(select(User).where(User.email == email))
    if user is not None:
        now = utcnow()
        recent = db.scalar(
            select(PasswordResetToken.id)
            .where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.created_at > now - timedelta(seconds=RESET_COOLDOWN_SECONDS),
            )
            .limit(1)
        )
        if recent is None:
            token = secrets.token_urlsafe(32)
            db.execute(
                update(PasswordResetToken)
                .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
                .values(used_at=now)  # an older, unused link stops working
            )
            db.add(
                PasswordResetToken(
                    user_id=user.id,
                    token_hash=hash_reset_token(token),
                    created_at=now,
                    expires_at=now + timedelta(minutes=RESET_TOKEN_MINUTES),
                )
            )
            db.commit()
            background.add_task(send_reset_email, user.email, token)

    return {
        "message": "If an account exists for that email, we have sent a link to reset the password. "
        f"It works for {RESET_TOKEN_MINUTES} minutes."
    }


@router.post("/reset-password")
def reset_password(body: ResetPassword, db: Session = Depends(get_db)):
    """
    Set a new password with the token from the emailed link. Each link works
    once, and only until it expires. On success the user is signed in: the
    response is the same as login's.
    """
    used = AuthError(
        400, "reset_token_used", "This reset link was already used or replaced by a newer one. Ask for a new one if you still need it."
    )
    row = db.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_reset_token(body.token.strip()))
    )
    if row is None:
        raise AuthError(400, "invalid_reset_token", "This reset link is not valid. Ask for a new one.")
    if row.used_at is not None:
        raise used
    now = utcnow()
    if row.expires_at <= now:
        raise AuthError(400, "reset_token_expired", "This reset link has expired. Ask for a new one.")

    # Checked before the link is used up, so a too-short password can be fixed and tried again.
    check_new_password(body.password)

    # Claim the link. If two requests arrive together only one can change the row.
    claimed = db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.id == row.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    if claimed.rowcount != 1:
        db.rollback()
        raise used

    user = db.get(User, row.user_id)
    user.password_hash = hash_password(body.password)
    db.execute(  # any other outstanding links for this account are done too
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    db.commit()
    db.refresh(user)
    return token_response(user)
