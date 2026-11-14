"""
KV-53: password reset. Ask for a link by email, set a new password with it.
The link works once, for a limited time, and asking never reveals whether an
address has an account.
"""

import hashlib
import logging
import re
from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select

import auth
import mailer
import settings
from conftest import PASSWORD
from models import PasswordResetToken, User, utcnow

NEW_PASSWORD = "a brand new passphrase"
TOKEN_IN_LINK = re.compile(r"\?reset_token=([A-Za-z0-9_-]+)")


@pytest.fixture
def outbox(monkeypatch):
    """Collects the emails the app would send: a list of (to, subject, body)."""
    sent = []
    monkeypatch.setattr(auth, "send_email", lambda to, subject, body: sent.append((to, subject, body)))
    return sent


@pytest.fixture
def no_cooldown(monkeypatch):
    monkeypatch.setattr(auth, "RESET_COOLDOWN_SECONDS", 0)


def forgot(client, email):
    return client.post("/auth/forgot-password", json={"email": email})


def reset(client, token, password=NEW_PASSWORD):
    return client.post("/auth/reset-password", json={"token": token, "password": password})


def login(client, email, password):
    return client.post("/auth/login", json={"email": email, "password": password})


def token_from(outbox, index=-1):
    to, _subject, body = outbox[index]
    return TOKEN_IN_LINK.search(body).group(1)


def assert_error(response, status, code):
    assert response.status_code == status, response.text
    body = response.json()
    assert body["code"] == code, body
    assert body["detail"]


# --- asking for a link --------------------------------------------------------


def test_a_link_is_emailed_to_an_existing_account(anonymous_client, client, outbox):
    response = forgot(anonymous_client, client.email)
    assert response.status_code == 202
    assert "message" in response.json()

    assert len(outbox) == 1
    to, subject, body = outbox[0]
    assert to == client.email
    assert "password" in subject.lower()
    assert f"{settings.FRONTEND_URL}/?reset_token=" in body
    assert f"{settings.RESET_TOKEN_MINUTES} minutes" in body


def test_an_unknown_address_gets_the_same_answer_and_no_email(anonymous_client, client, outbox):
    known = forgot(anonymous_client, client.email)
    unknown = forgot(anonymous_client, "nobody-here@example.test")

    assert unknown.status_code == known.status_code == 202
    assert unknown.json() == known.json(), "the answer must not reveal which addresses have accounts"
    assert [to for to, _, _ in outbox] == [client.email]


def test_the_address_is_matched_without_regard_to_case(anonymous_client, client, outbox):
    forgot(anonymous_client, f"  {client.email.upper()} ")
    assert [to for to, _, _ in outbox] == [client.email]


def test_a_badly_formed_address_is_refused(anonymous_client, outbox):
    assert_error(forgot(anonymous_client, "not an email"), 422, "invalid_email")
    assert outbox == []


def test_the_placeholder_user_cannot_be_reset(anonymous_client, db, outbox):
    # The default user (KV-42) owns old documents and has no usable password.
    assert_error(forgot(anonymous_client, "default@knowledgevault.local"), 422, "invalid_email")
    assert outbox == []


def test_only_a_hash_of_the_token_is_stored(anonymous_client, client, db, outbox):
    forgot(anonymous_client, client.email)
    token = token_from(outbox)

    rows = db.scalars(select(PasswordResetToken).where(PasswordResetToken.user_id == client.user_id)).all()
    assert len(rows) == 1
    assert rows[0].token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert token not in rows[0].token_hash
    expires_in = rows[0].expires_at - rows[0].created_at
    assert expires_in == timedelta(minutes=settings.RESET_TOKEN_MINUTES)
    assert rows[0].used_at is None


def test_asking_twice_in_a_minute_sends_one_email(anonymous_client, client, outbox):
    first = forgot(anonymous_client, client.email)
    second = forgot(anonymous_client, client.email)
    assert first.json() == second.json()
    assert len(outbox) == 1


# --- setting a new password ---------------------------------------------------


def test_reset_end_to_end(anonymous_client, client, outbox):
    forgot(anonymous_client, client.email)
    response = reset(anonymous_client, token_from(outbox))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user"] == {"id": client.user_id, "email": client.email}
    me = anonymous_client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200, "the reset signs the user in"

    assert login(anonymous_client, client.email, NEW_PASSWORD).status_code == 200
    assert_error(login(anonymous_client, client.email, PASSWORD), 401, "invalid_credentials")


def test_the_new_password_is_stored_hashed(anonymous_client, client, db, outbox):
    forgot(anonymous_client, client.email)
    reset(anonymous_client, token_from(outbox))
    stored = db.scalar(select(User.password_hash).where(User.id == client.user_id))
    assert NEW_PASSWORD not in stored
    assert auth.verify_password(NEW_PASSWORD, stored)


def test_a_link_works_only_once(anonymous_client, client, outbox):
    forgot(anonymous_client, client.email)
    token = token_from(outbox)
    assert reset(anonymous_client, token).status_code == 200

    again = reset(anonymous_client, token, "someone elses password")
    assert_error(again, 400, "reset_token_used")
    assert login(anonymous_client, client.email, NEW_PASSWORD).status_code == 200
    assert_error(login(anonymous_client, client.email, "someone elses password"), 401, "invalid_credentials")


def test_an_expired_link_is_refused(anonymous_client, client, db, outbox):
    forgot(anonymous_client, client.email)
    token = token_from(outbox)
    row = db.scalar(select(PasswordResetToken).where(PasswordResetToken.user_id == client.user_id))
    row.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()

    assert_error(reset(anonymous_client, token), 400, "reset_token_expired")
    assert login(anonymous_client, client.email, PASSWORD).status_code == 200, "the old password still works"


def test_a_made_up_token_is_refused(anonymous_client, client, outbox):
    forgot(anonymous_client, client.email)
    assert_error(reset(anonymous_client, "not-a-real-token"), 400, "invalid_reset_token")
    assert_error(reset(anonymous_client, ""), 400, "invalid_reset_token")


def test_a_weak_password_is_refused_without_using_up_the_link(anonymous_client, client, outbox):
    forgot(anonymous_client, client.email)
    token = token_from(outbox)

    assert_error(reset(anonymous_client, token, "short"), 422, "weak_password")
    assert_error(reset(anonymous_client, token, "x" * 80), 422, "password_too_long")
    assert reset(anonymous_client, token).status_code == 200, "the same link still works with a good password"


def test_a_newer_link_replaces_the_older_one(anonymous_client, client, outbox, no_cooldown):
    forgot(anonymous_client, client.email)
    forgot(anonymous_client, client.email)
    assert len(outbox) == 2
    old, new = token_from(outbox, 0), token_from(outbox, 1)
    assert old != new

    assert_error(reset(anonymous_client, old), 400, "reset_token_used")
    assert reset(anonymous_client, new).status_code == 200


def test_using_a_link_ends_other_open_links(anonymous_client, client, db, outbox, no_cooldown):
    forgot(anonymous_client, client.email)
    token = token_from(outbox)
    # A second, still-unused link for the same account (as if one had been made in between).
    db.add(
        PasswordResetToken(
            user_id=client.user_id,
            token_hash=hashlib.sha256(b"another").hexdigest(),
            expires_at=utcnow() + timedelta(minutes=10),
        )
    )
    db.commit()

    assert reset(anonymous_client, token).status_code == 200
    assert_error(reset(anonymous_client, "another"), 400, "reset_token_used")


def test_a_link_belongs_to_one_account(anonymous_client, client, other_client, outbox):
    forgot(anonymous_client, client.email)
    reset(anonymous_client, token_from(outbox))
    assert login(anonymous_client, other_client.email, PASSWORD).status_code == 200, "nobody else was touched"


def test_deleting_an_account_removes_its_links(anonymous_client, client, db, outbox):
    forgot(anonymous_client, client.email)
    db.expire_all()
    db.delete(db.get(User, client.user_id))
    db.commit()
    assert db.scalar(select(PasswordResetToken.id).where(PasswordResetToken.user_id == client.user_id)) is None


# --- the email itself ---------------------------------------------------------


def test_without_a_mail_server_the_message_is_logged(monkeypatch, caplog):
    monkeypatch.setattr(mailer, "SMTP_HOST", "")
    with caplog.at_level(logging.WARNING, logger="knowledgevault.mail"):
        sent = mailer.send_email("a@example.test", "Hello", "The link is http://x/?reset_token=abc")
    assert sent is False
    assert "http://x/?reset_token=abc" in caplog.text
    assert "a@example.test" in caplog.text


@pytest.fixture
def smtp(monkeypatch):
    """A stand-in mail server. Returns the mock for smtplib.SMTP."""
    server = MagicMock()
    server.__enter__.return_value = server
    factory = MagicMock(return_value=server)
    monkeypatch.setattr(mailer.smtplib, "SMTP", factory)
    monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", factory)
    monkeypatch.setattr(mailer, "SMTP_HOST", "smtp.example.test")
    monkeypatch.setattr(mailer, "SMTP_PORT", 587)
    monkeypatch.setattr(mailer, "SMTP_USER", "kv@example.test")
    monkeypatch.setattr(mailer, "SMTP_PASSWORD", "app-password")
    monkeypatch.setattr(mailer, "MAIL_FROM", "KnowledgeVault <kv@example.test>")
    factory.server = server
    return factory


def test_with_a_mail_server_the_message_is_sent(smtp):
    assert mailer.send_email("a@example.test", "Hello", "Body text") is True

    smtp.assert_called_once()
    assert smtp.call_args.args[:2] == ("smtp.example.test", 587)
    smtp.server.starttls.assert_called_once()
    smtp.server.login.assert_called_once_with("kv@example.test", "app-password")
    message = smtp.server.send_message.call_args.args[0]
    assert message["To"] == "a@example.test"
    assert message["From"] == "KnowledgeVault <kv@example.test>"
    assert message["Subject"] == "Hello"
    assert "Body text" in message.get_content()


def test_a_mail_server_that_fails_does_not_raise(smtp, caplog):
    smtp.server.send_message.side_effect = OSError("connection refused")
    with caplog.at_level(logging.ERROR, logger="knowledgevault.mail"):
        assert mailer.send_email("a@example.test", "Hello", "Body") is False
    assert "a@example.test" in caplog.text


def test_a_request_still_succeeds_when_the_mail_server_is_down(anonymous_client, client, smtp):
    smtp.server.send_message.side_effect = OSError("connection refused")
    assert forgot(anonymous_client, client.email).status_code == 202


# --- settings and docs --------------------------------------------------------


def test_the_reset_settings_have_sensible_values():
    assert settings.FRONTEND_URL.startswith("http") and not settings.FRONTEND_URL.endswith("/")
    assert 5 <= settings.RESET_TOKEN_MINUTES <= 24 * 60


def test_the_new_error_codes_are_documented():
    for code in ("invalid_reset_token", "reset_token_expired", "reset_token_used"):
        assert code in auth.__doc__
