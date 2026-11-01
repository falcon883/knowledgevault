"""
KV-37: settings come from the environment, and /health checks the database.
"""

import pytest

import main
import settings
from database import get_db


# --- settings.py -----------------------------------------------------------


def test_missing_required_setting_explains_how_to_fix_it(monkeypatch):
    monkeypatch.delenv("KV_TEST_SETTING", raising=False)
    with pytest.raises(settings.ConfigError) as error:
        settings.require_env("KV_TEST_SETTING")
    message = str(error.value)
    assert "KV_TEST_SETTING" in message
    assert ".env.example" in message


def test_blank_required_setting_counts_as_missing(monkeypatch):
    monkeypatch.setenv("KV_TEST_SETTING", "   ")
    with pytest.raises(settings.ConfigError):
        settings.require_env("KV_TEST_SETTING")


def test_required_setting_is_returned_when_set(monkeypatch):
    monkeypatch.setenv("KV_TEST_SETTING", "  value  ")
    assert settings.require_env("KV_TEST_SETTING") == "value"


def test_no_database_credentials_are_hard_coded():
    # The old default URL contained the username and password. The setting
    # must now come from the environment, never from a literal in the code.
    from pathlib import Path

    source = Path(settings.__file__).parent.joinpath("database.py").read_text()
    assert "postgresql+psycopg2://" not in source
    assert "knowledgevault:knowledgevault" not in source


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("http://localhost:5173", ["http://localhost:5173"]),
        (
            "http://localhost:5173, https://app.example.com",
            ["http://localhost:5173", "https://app.example.com"],
        ),
        ("https://app.example.com/", ["https://app.example.com"]),
        (" , http://a.test ,, ", ["http://a.test"]),
        ("", []),
        (None, []),
    ],
)
def test_parse_origins(raw, expected):
    assert settings.parse_origins(raw) == expected


def test_cors_origins_always_has_at_least_one_entry():
    assert settings.CORS_ORIGINS


# --- CORS --------------------------------------------------------------------


def test_allowed_origin_gets_cors_headers(client):
    origin = settings.CORS_ORIGINS[0]
    response = client.get("/health", headers={"Origin": origin})
    assert response.headers.get("access-control-allow-origin") == origin


def test_unknown_origin_gets_no_cors_headers(client):
    response = client.get("/health", headers={"Origin": "http://not-allowed.example"})
    assert "access-control-allow-origin" not in response.headers


# --- /health -----------------------------------------------------------------


def test_health_reports_database_and_model(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert isinstance(body["model_loaded"], bool)
    assert "max_upload_mb" in body


class _BrokenSession:
    """Stands in for a database session whose server is unreachable."""

    def execute(self, *args, **kwargs):
        raise ConnectionError("database is down")

    def close(self):
        pass


def test_health_returns_503_when_the_database_is_down(client):
    main.app.dependency_overrides[get_db] = lambda: _BrokenSession()
    try:
        response = client.get("/health")
    finally:
        main.app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "error"
    assert body["database"] == "unavailable"
    # The rest of the report is still there, so you can see what else is up.
    assert "model_loaded" in body


def test_health_does_not_fail_when_only_the_model_is_missing(client, monkeypatch):
    monkeypatch.setattr(main.embeddings, "is_loaded", lambda: False)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["model_loaded"] is False
