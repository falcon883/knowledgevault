"""
KV-42: accounts. Signup and login, tokens, and each user seeing only their own
documents.
"""

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import select

import auth
import settings
from conftest import PASSWORD
from init_db import DEFAULT_USER_EMAIL
from models import User

TEXT = "Sourdough starters need regular feeding with flour and water to stay lively."


def signup(client, email="new@example.test", password=PASSWORD):
    return client.post("/auth/signup", json={"email": email, "password": password})


def login(client, email, password=PASSWORD):
    return client.post("/auth/login", json={"email": email, "password": password})


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def assert_error(response, status, code):
    assert response.status_code == status, response.text
    body = response.json()
    assert body["code"] == code
    assert body["detail"]


# --- signup ------------------------------------------------------------------


def test_signup_returns_a_token_and_the_user(anonymous_client):
    response = signup(anonymous_client, "Kv42.Signup@Example.test")
    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == "kv42.signup@example.test", "emails are stored in lowercase"
    assert "password" not in str(body).lower()

    me = anonymous_client.get("/auth/me", headers=bearer(body["access_token"]))
    assert me.status_code == 200
    assert me.json() == body["user"]


def test_the_password_is_stored_hashed(anonymous_client, db):
    signup(anonymous_client, "kv42.hash@example.test", "a very secret phrase")
    stored = db.scalar(select(User.password_hash).where(User.email == "kv42.hash@example.test"))
    assert "a very secret phrase" not in stored
    assert stored.startswith("$2"), "expected a bcrypt hash"
    assert auth.verify_password("a very secret phrase", stored)
    assert not auth.verify_password("another phrase entirely", stored)


def test_two_users_with_the_same_password_get_different_hashes(anonymous_client, db):
    signup(anonymous_client, "kv42.one@example.test")
    signup(anonymous_client, "kv42.two@example.test")
    hashes = db.scalars(select(User.password_hash).where(User.email.like("kv42.%@example.test"))).all()
    assert len(hashes) == 2 and hashes[0] != hashes[1], "each hash has its own salt"


def test_an_email_can_only_sign_up_once(anonymous_client):
    assert signup(anonymous_client, "kv42.dup@example.test").status_code == 201
    assert_error(signup(anonymous_client, "kv42.dup@example.test"), 409, "email_taken")
    assert_error(signup(anonymous_client, "  KV42.DUP@example.test "), 409, "email_taken")


@pytest.mark.parametrize(
    "email", ["", "plainaddress", "no-at-sign.example.test", "two@@example.test", "a b@example.test", "x@y"]
)
def test_signup_rejects_an_invalid_email(anonymous_client, email):
    assert_error(signup(anonymous_client, email), 422, "invalid_email")


def test_signup_rejects_the_reserved_placeholder_domain(anonymous_client):
    assert_error(signup(anonymous_client, "someone@knowledgevault.local"), 422, "invalid_email")


def test_signup_rejects_a_short_password(anonymous_client):
    assert_error(signup(anonymous_client, "kv42.short@example.test", "short"), 422, "weak_password")
    assert signup(anonymous_client, "kv42.eight@example.test", "12345678").status_code == 201


def test_signup_rejects_a_password_bcrypt_cannot_hold(anonymous_client):
    assert_error(signup(anonymous_client, "kv42.long@example.test", "x" * 73), 422, "password_too_long")
    assert signup(anonymous_client, "kv42.max@example.test", "x" * 72).status_code == 201


# --- login -------------------------------------------------------------------


def test_login_with_the_right_password(anonymous_client):
    signup(anonymous_client, "kv42.login@example.test")
    response = login(anonymous_client, "KV42.Login@example.test ")
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == "kv42.login@example.test"
    assert anonymous_client.get("/auth/me", headers=bearer(body["access_token"])).status_code == 200


def test_login_gives_the_same_answer_for_a_wrong_password_and_an_unknown_email(anonymous_client):
    signup(anonymous_client, "kv42.known@example.test")
    wrong_password = login(anonymous_client, "kv42.known@example.test", "not the password")
    unknown_email = login(anonymous_client, "kv42.nobody@example.test")
    assert_error(wrong_password, 401, "invalid_credentials")
    assert_error(unknown_email, 401, "invalid_credentials")
    assert wrong_password.json() == unknown_email.json(), "must not reveal which emails have accounts"


def test_nobody_can_sign_in_as_the_default_user(anonymous_client, db):
    # A database that has been upgraded already has this user; make sure it exists.
    if db.scalar(select(User.id).where(User.email == DEFAULT_USER_EMAIL)) is None:
        db.add(User(email=DEFAULT_USER_EMAIL, password_hash="!"))
        db.commit()
    for password in ["!", "", PASSWORD]:
        assert_error(login(anonymous_client, DEFAULT_USER_EMAIL, password), 401, "invalid_credentials")


# --- tokens ------------------------------------------------------------------


def test_requests_without_a_token_are_refused(anonymous_client):
    response = anonymous_client.get("/documents")
    assert_error(response, 401, "not_authenticated")
    assert response.headers["www-authenticate"] == "Bearer"


def test_a_garbled_token_is_refused(anonymous_client):
    assert_error(anonymous_client.get("/documents", headers=bearer("not.a.token")), 401, "invalid_token")


def test_a_token_signed_with_another_key_is_refused(anonymous_client, client):
    forged = jwt.encode(
        {"sub": str(client.user_id), "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        "some-other-key-that-is-long-enough-to-sign-with",
        algorithm="HS256",
    )
    assert_error(anonymous_client.get("/documents", headers=bearer(forged)), 401, "invalid_token")


def test_an_unsigned_token_is_refused(anonymous_client, client):
    unsigned = jwt.encode({"sub": str(client.user_id), "exp": 4102444800}, key=None, algorithm="none")
    assert_error(anonymous_client.get("/documents", headers=bearer(unsigned)), 401, "invalid_token")


def test_an_expired_token_says_so(anonymous_client, client):
    expired = jwt.encode(
        {"sub": str(client.user_id), "exp": datetime.now(timezone.utc) - timedelta(seconds=5)},
        settings.SECRET_KEY,
        algorithm="HS256",
    )
    assert_error(anonymous_client.get("/documents", headers=bearer(expired)), 401, "token_expired")


def test_a_token_without_an_expiry_is_refused(anonymous_client, client):
    forever = jwt.encode({"sub": str(client.user_id)}, settings.SECRET_KEY, algorithm="HS256")
    assert_error(anonymous_client.get("/documents", headers=bearer(forever)), 401, "invalid_token")


def test_a_token_for_a_user_that_no_longer_exists_is_refused(anonymous_client, db):
    token = signup(anonymous_client, "kv42.gone@example.test").json()["access_token"]
    db.delete(db.scalar(select(User).where(User.email == "kv42.gone@example.test")))
    db.commit()
    assert_error(anonymous_client.get("/auth/me", headers=bearer(token)), 401, "invalid_token")


def test_a_token_that_is_not_a_bearer_header_is_refused(anonymous_client, client):
    token = client.headers["Authorization"].split()[1]
    response = anonymous_client.get("/documents", headers={"Authorization": f"Basic {token}"})
    assert_error(response, 401, "not_authenticated")


PROTECTED = [
    ("post", "/upload"),
    ("get", "/documents"),
    ("get", "/documents/1"),
    ("delete", "/documents/1"),
    ("get", "/tags"),
    ("post", "/search"),
    ("get", "/auth/me"),
]


@pytest.mark.parametrize("method, path", PROTECTED)
def test_every_data_route_needs_a_token(anonymous_client, method, path):
    response = getattr(anonymous_client, method)(path)
    assert_error(response, 401, "not_authenticated")


def test_health_and_the_docs_stay_public(anonymous_client):
    assert anonymous_client.get("/health").status_code == 200
    assert anonymous_client.get("/docs").status_code == 200
    assert anonymous_client.get("/openapi.json").status_code == 200


# --- one user cannot see another's documents ------------------------------------


def upload_as(client, name="kv42_notes.txt", text_=TEXT, **params):
    response = client.post("/upload", files={"file": (name, text_.encode(), "text/plain")}, params=params)
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_a_user_sees_only_their_own_documents(client, other_client):
    mine = upload_as(client)
    theirs = upload_as(other_client, "kv42_other.txt", "Marathon training plans build weekly mileage slowly.")

    assert [d["id"] for d in client.get("/documents").json()] == [mine]
    assert [d["id"] for d in other_client.get("/documents").json()] == [theirs]


def test_another_users_document_looks_like_it_does_not_exist(client, other_client):
    mine = upload_as(client)
    assert other_client.get(f"/documents/{mine}").status_code == 404
    assert other_client.delete(f"/documents/{mine}").status_code == 404
    # still there, and still readable by its owner
    assert client.get(f"/documents/{mine}").status_code == 200
    assert [d["id"] for d in client.get("/documents").json()] == [mine]


def test_search_never_returns_another_users_documents(client, other_client):
    mine = upload_as(client)
    query = {"query": "how do I feed a sourdough starter", "min_score": 0}

    own = client.post("/search", json=query).json()
    assert [hit["document_id"] for hit in own["results"]] == [mine]

    theirs = other_client.post("/search", json=query).json()
    assert theirs["count"] == 0 and theirs["results"] == []


def test_tags_count_only_the_callers_documents(client, other_client, db):
    from models import Document

    upload_as(client)
    doc = db.get(Document, upload_as(other_client, "kv42_tagged.txt", "Compost needs green and brown waste."))
    doc.tags = "kv42-private-tag"
    db.commit()

    assert "kv42-private-tag" not in [t["tag"] for t in client.get("/tags").json()]
    assert "kv42-private-tag" in [t["tag"] for t in other_client.get("/tags").json()]


def test_duplicates_are_only_detected_within_one_users_documents(client, other_client):
    first = upload_as(client)

    # the same file from someone else is not a duplicate, and does not reveal that it exists
    other = other_client.post("/upload", files={"file": ("kv42_copy.txt", TEXT.encode(), "text/plain")})
    assert other.status_code == 200

    # but the first user still gets the warning for their own copy
    again = client.post("/upload", files={"file": ("kv42_again.txt", TEXT.encode(), "text/plain")})
    assert again.status_code == 409
    assert again.json()["existing"]["id"] == first


def test_a_user_can_delete_their_own_document(client):
    mine = upload_as(client)
    assert client.delete(f"/documents/{mine}").status_code == 200
    assert client.get("/documents").json() == []


def test_signing_in_again_shows_the_same_documents(client, anonymous_client):
    mine = upload_as(client)
    token = login(anonymous_client, client.email).json()["access_token"]
    listed = anonymous_client.get("/documents", headers=bearer(token)).json()
    assert [d["id"] for d in listed] == [mine]
