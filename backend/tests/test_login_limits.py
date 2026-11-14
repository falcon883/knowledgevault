"""
KV-54: limits on failed sign-ins. Too many wrong passwords for one email, or
from one address, get a 429 that ends by itself. Correct sign-ins are never
slowed down.
"""

import pytest

import auth
import ratelimit
import settings
from conftest import PASSWORD
from ratelimit import FailureLimiter, LoginLimits

WRONG = "definitely not the password"


class Clock:
    """A clock the tests move by hand, in seconds."""

    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


# --- FailureLimiter on its own -----------------------------------------------


def test_a_key_may_fail_up_to_the_limit_and_is_then_refused():
    clock = Clock()
    limiter = FailureLimiter(3, 600, clock)
    for _ in range(3):
        assert limiter.retry_after("a") == 0
        limiter.record("a")
    assert limiter.retry_after("a") == 600
    assert limiter.retry_after("b") == 0, "other keys are not affected"


def test_the_wait_counts_down_and_then_ends():
    clock = Clock()
    limiter = FailureLimiter(2, 600, clock)
    limiter.record("a")
    limiter.record("a")
    clock.advance(100)
    assert limiter.retry_after("a") == 500
    clock.advance(499)
    assert limiter.retry_after("a") == 1
    clock.advance(1)
    assert limiter.retry_after("a") == 0


def test_the_window_slides_with_each_failure():
    clock = Clock()
    limiter = FailureLimiter(3, 300, clock)
    for _ in range(3):  # failures at 0, 100 and 200
        limiter.record("a")
        clock.advance(100)
    assert limiter.retry_after("a") == 0  # now t=300: the failure from t=0 has expired
    limiter.record("a")  # a new failure at 300 refills the window: 100, 200, 300
    assert limiter.retry_after("a") == 100  # until the one from t=100 is 300 seconds old


def test_clear_forgets_a_key():
    limiter = FailureLimiter(1, 600, Clock())
    limiter.record("a")
    assert limiter.retry_after("a")
    limiter.clear("a")
    assert limiter.retry_after("a") == 0


def test_memory_is_bounded(monkeypatch):
    monkeypatch.setattr(ratelimit, "MAX_KEYS", 3)
    limiter = FailureLimiter(5, 600, Clock())
    for index in range(10):
        limiter.record(f"key{index}")
    assert len(limiter._failures) <= 3
    assert "key9" in limiter._failures, "the newest keys are kept"


def test_expired_keys_are_dropped_before_live_ones(monkeypatch):
    monkeypatch.setattr(ratelimit, "MAX_KEYS", 2)
    clock = Clock()
    limiter = FailureLimiter(5, 100, clock)
    limiter.record("old")
    clock.advance(200)
    limiter.record("live1")
    limiter.record("live2")
    assert set(limiter._failures) == {"live1", "live2"}


# --- /auth/login --------------------------------------------------------------


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def limits(monkeypatch, clock):
    """Small limits so the tests are short: 3 failures per email, 6 per address, a 10 minute window."""
    small = LoginLimits(max_per_email=3, max_per_ip=6, window=600, clock=clock)
    monkeypatch.setattr(auth, "login_limits", small)
    return small


def login(client, email, password=PASSWORD, ip=None):
    headers = {"X-Forwarded-For": ip} if ip else {}
    return client.post("/auth/login", json={"email": email, "password": password}, headers=headers)


def assert_blocked(response):
    assert response.status_code == 429, response.text
    body = response.json()
    assert body["code"] == "too_many_attempts"
    assert "try again in" in body["detail"].lower()
    assert 1 <= int(response.headers["retry-after"]) <= 600
    return body


def test_too_many_wrong_passwords_get_a_429(anonymous_client, client, limits):
    for _ in range(3):
        assert login(anonymous_client, client.email, WRONG).status_code == 401
    body = assert_blocked(login(anonymous_client, client.email, WRONG))
    assert "10 minutes" in body["detail"]


def test_the_right_password_is_refused_during_a_lockout(anonymous_client, client, limits):
    for _ in range(3):
        login(anonymous_client, client.email, WRONG)
    assert_blocked(login(anonymous_client, client.email, PASSWORD))


def test_the_limit_resets_after_the_wait(anonymous_client, client, limits, clock):
    for _ in range(3):
        login(anonymous_client, client.email, WRONG)
    assert_blocked(login(anonymous_client, client.email))

    clock.advance(601)
    assert login(anonymous_client, client.email).status_code == 200
    assert login(anonymous_client, client.email, WRONG).status_code == 401, "and wrong passwords count again from zero"


def test_refused_attempts_do_not_extend_the_lockout(anonymous_client, client, limits, clock):
    for _ in range(3):
        login(anonymous_client, client.email, WRONG)
    for _ in range(5):  # someone keeps trying through the lockout
        clock.advance(100)
        assert_blocked(login(anonymous_client, client.email, WRONG))
    clock.advance(101)  # 601 seconds after the first failures
    assert login(anonymous_client, client.email).status_code == 200


def test_normal_sign_ins_are_not_affected(anonymous_client, client, limits):
    for _ in range(20):
        assert login(anonymous_client, client.email).status_code == 200


def test_a_successful_sign_in_forgets_the_failures(anonymous_client, client, limits):
    for _ in range(2):
        login(anonymous_client, client.email, WRONG)
    assert login(anonymous_client, client.email).status_code == 200
    for _ in range(2):  # two more would have made four in a row without the success
        assert login(anonymous_client, client.email, WRONG).status_code == 401
    assert login(anonymous_client, client.email).status_code == 200


def test_an_unknown_email_is_limited_the_same_way(anonymous_client, client, limits):
    """So the limit cannot be used to tell which emails have accounts."""
    for _ in range(3):
        assert login(anonymous_client, "nobody@example.test", WRONG).status_code == 401
    unknown = assert_blocked(login(anonymous_client, "nobody@example.test", WRONG))

    limits.reset()
    for _ in range(3):
        login(anonymous_client, client.email, WRONG)
    known = assert_blocked(login(anonymous_client, client.email, WRONG))
    assert unknown == known


def test_the_email_is_matched_without_regard_to_case_or_spaces(anonymous_client, client, limits):
    for variant in (client.email.upper(), f" {client.email} ", client.email):
        login(anonymous_client, variant, WRONG)
    assert_blocked(login(anonymous_client, client.email, PASSWORD))


def test_one_locked_email_does_not_lock_the_others(anonymous_client, client, other_client, limits):
    for _ in range(3):
        login(anonymous_client, client.email, WRONG)
    assert_blocked(login(anonymous_client, client.email))
    assert login(anonymous_client, other_client.email).status_code == 200


def test_many_failures_from_one_address_lock_that_address(anonymous_client, client, limits):
    for index in range(6):  # a different email each time, so no email reaches its own limit
        assert login(anonymous_client, f"guess{index}@example.test", WRONG, ip="203.0.113.7").status_code == 401
    assert_blocked(login(anonymous_client, client.email, PASSWORD, ip="203.0.113.7"))
    assert login(anonymous_client, client.email, PASSWORD, ip="203.0.113.8").status_code == 200, "another address is fine"


def test_the_address_limit_also_ends(anonymous_client, client, limits, clock):
    for index in range(6):
        login(anonymous_client, f"guess{index}@example.test", WRONG, ip="203.0.113.7")
    clock.advance(601)
    assert login(anonymous_client, client.email, PASSWORD, ip="203.0.113.7").status_code == 200


def test_the_address_is_the_last_entry_of_x_forwarded_for(anonymous_client, client, limits):
    """The proxy appends the address it saw; anything before that came from the client."""
    for index in range(6):
        login(anonymous_client, f"guess{index}@example.test", WRONG, ip=f"10.9.9.{index}, 198.51.100.4")
    assert_blocked(login(anonymous_client, client.email, ip="1.2.3.4, 198.51.100.4"))
    assert login(anonymous_client, client.email, ip="198.51.100.4, 1.2.3.4").status_code == 200


def test_without_a_proxy_the_sockets_address_is_used(anonymous_client, client, limits):
    for index in range(6):
        login(anonymous_client, f"guess{index}@example.test", WRONG)
    assert_blocked(login(anonymous_client, client.email))


def test_a_sign_in_of_your_own_does_not_reset_the_address_count(anonymous_client, client, other_client, monkeypatch, clock):
    """Otherwise someone could guess forever by signing in to their own account in between."""
    monkeypatch.setattr(auth, "login_limits", LoginLimits(max_per_email=50, max_per_ip=4, window=600, clock=clock))
    for index in range(3):
        login(anonymous_client, f"guess{index}@example.test", WRONG)
    assert login(anonymous_client, other_client.email).status_code == 200
    login(anonymous_client, "guess3@example.test", WRONG)
    assert_blocked(login(anonymous_client, other_client.email))


def test_malformed_requests_are_not_counted(anonymous_client, client, limits):
    for _ in range(5):
        assert anonymous_client.post("/auth/login", json={"email": client.email}).status_code == 422
    assert login(anonymous_client, client.email).status_code == 200


def test_a_single_minute_is_not_pluralised(anonymous_client, client, monkeypatch, clock):
    monkeypatch.setattr(auth, "login_limits", LoginLimits(1, 10, window=60, clock=clock))
    login(anonymous_client, client.email, WRONG)
    detail = assert_blocked_short(login(anonymous_client, client.email))
    assert "1 minute." in detail


def assert_blocked_short(response):
    assert response.status_code == 429
    return response.json()["detail"]


def test_signup_and_reset_are_not_affected(anonymous_client, client, limits):
    for _ in range(3):
        login(anonymous_client, client.email, WRONG)
    assert_blocked(login(anonymous_client, client.email))
    assert anonymous_client.post("/auth/forgot-password", json={"email": client.email}).status_code == 202


# --- settings and docs ---------------------------------------------------------


def test_the_default_limits_are_sensible():
    assert 3 <= settings.LOGIN_MAX_FAILURES_PER_EMAIL <= 10
    assert settings.LOGIN_MAX_FAILURES_PER_IP >= settings.LOGIN_MAX_FAILURES_PER_EMAIL
    assert 1 <= settings.LOGIN_WINDOW_MINUTES <= 60


def test_the_live_limits_use_the_settings():
    live = auth.login_limits
    assert live.by_email.max_failures == settings.LOGIN_MAX_FAILURES_PER_EMAIL
    assert live.by_ip.max_failures == settings.LOGIN_MAX_FAILURES_PER_IP
    assert live.by_email.window == settings.LOGIN_WINDOW_MINUTES * 60


def test_the_error_code_is_documented():
    assert "too_many_attempts" in auth.__doc__
