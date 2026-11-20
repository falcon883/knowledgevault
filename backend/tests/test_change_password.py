"""
KV-62: a signed-in user changes their password. The current password is
required, a wrong one is 400 (never 401), and wrong guesses are limited like
sign-in failures.
"""

import auth
from conftest import PASSWORD
from models import PasswordResetToken, utcnow

NEW_PASSWORD = "a brand new passphrase"


def change(client, current=PASSWORD, new=NEW_PASSWORD):
    return client.post("/auth/change-password", json={"current_password": current, "new_password": new})


def login(client, email, password):
    return client.post("/auth/login", json={"email": email, "password": password})


def assert_error(response, status, code):
    assert response.status_code == status, response.text
    body = response.json()
    assert body["code"] == code, body
    assert body["detail"]


def test_password_is_changed(client, anonymous_client):
    response = change(client)
    assert response.status_code == 200
    assert response.json() == {"message": "Password changed."}
    assert login(anonymous_client, client.email, NEW_PASSWORD).status_code == 200
    assert_error(login(anonymous_client, client.email, PASSWORD), 401, "invalid_credentials")


def test_user_stays_signed_in(client):
    assert change(client).status_code == 200
    assert client.get("/auth/me").status_code == 200


def test_it_can_be_changed_again_with_the_new_password(client, anonymous_client):
    assert change(client).status_code == 200
    assert change(client, current=NEW_PASSWORD, new="yet another passphrase").status_code == 200
    assert login(anonymous_client, client.email, "yet another passphrase").status_code == 200


def test_signed_out_is_401(anonymous_client):
    assert_error(change(anonymous_client), 401, "not_authenticated")


def test_wrong_current_password_is_400_not_401(client, anonymous_client):
    assert_error(change(client, current="not my password"), 400, "wrong_password")
    # nothing changed
    assert login(anonymous_client, client.email, PASSWORD).status_code == 200
    assert client.get("/auth/me").status_code == 200


def test_weak_new_password(client):
    assert_error(change(client, new="short"), 422, "weak_password")


def test_too_long_new_password(client):
    assert_error(change(client, new="x" * 73), 422, "password_too_long")


def test_new_password_must_differ(client):
    assert_error(change(client, new=PASSWORD), 422, "same_password")


def test_blank_current_password_is_wrong(client):
    assert_error(change(client, current=""), 400, "wrong_password")


def test_overlong_current_password_is_wrong_not_an_error(client):
    assert_error(change(client, current="x" * 200), 400, "wrong_password")


def test_missing_fields_are_rejected(client):
    assert client.post("/auth/change-password", json={"new_password": NEW_PASSWORD}).status_code == 422


def test_users_only_change_their_own_password(client, other_client, anonymous_client):
    assert change(client).status_code == 200
    assert login(anonymous_client, other_client.email, PASSWORD).status_code == 200


def test_unused_reset_links_stop_working(client, db):
    from datetime import timedelta

    now = utcnow()
    db.add(
        PasswordResetToken(
            user_id=client.user_id, token_hash="a" * 64, created_at=now, expires_at=now + timedelta(minutes=30)
        )
    )
    db.commit()
    assert change(client).status_code == 200
    db.expire_all()
    row = db.query(PasswordResetToken).filter_by(user_id=client.user_id).one()
    assert row.used_at is not None


def test_wrong_guesses_are_limited(client, anonymous_client, monkeypatch):
    small = auth.LoginLimits(max_per_email=3, max_per_ip=50, window=600)
    monkeypatch.setattr(auth, "login_limits", small)
    for _ in range(3):
        assert_error(change(client, current="wrong guess"), 400, "wrong_password")
    refused = change(client, current="wrong guess")
    assert_error(refused, 429, "too_many_attempts")
    assert int(refused.headers["Retry-After"]) > 0
    assert "password attempts" in refused.json()["detail"]
    # during the lockout even the right password is refused, and nothing changes
    assert_error(change(client), 429, "too_many_attempts")
    assert login(anonymous_client, client.email, PASSWORD).status_code == 429


def test_a_successful_change_forgets_earlier_failures(client, monkeypatch):
    small = auth.LoginLimits(max_per_email=3, max_per_ip=50, window=600)
    monkeypatch.setattr(auth, "login_limits", small)
    for _ in range(2):
        assert_error(change(client, current="wrong guess"), 400, "wrong_password")
    assert change(client).status_code == 200
    for _ in range(2):
        assert_error(change(client, current="wrong guess"), 400, "wrong_password")


def test_failures_here_and_at_login_share_a_count(client, anonymous_client, monkeypatch):
    small = auth.LoginLimits(max_per_email=3, max_per_ip=50, window=600)
    monkeypatch.setattr(auth, "login_limits", small)
    for _ in range(2):
        assert_error(login(anonymous_client, client.email, "wrong guess"), 401, "invalid_credentials")
    assert_error(change(client, current="wrong guess"), 400, "wrong_password")
    assert_error(change(client), 429, "too_many_attempts")
