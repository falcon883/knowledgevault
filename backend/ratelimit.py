"""
KnowledgeVault backend - limits on failed sign-ins (KV-54).

Nothing used to stop someone trying passwords against /auth/login as fast as
they could. Failed attempts are now counted per email and per client address,
and once a count reaches its limit further attempts are refused (429) until
the oldest counted failure is `window` seconds old. So the wait is at most the
window, and it ends by itself.

Details that matter:

  * Only failures are counted. A correct password is never slowed down, and a
    successful sign-in forgets the failures for that email.
  * While a key is over its limit the password is not even checked, so a
    correct guess during a lockout gives the attacker nothing. Refused attempts
    are not counted, so the lockout does not extend itself.
  * Emails are counted whether or not they have an account, so the limit does
    not reveal which emails exist.
  * Counts live in memory, in this process. The server runs one process, so
    that is enough; a restart forgets them, and a second process would count
    on its own. Memory is bounded (see MAX_KEYS).
"""

import math
import threading
import time
from collections import deque
from collections.abc import Callable

MAX_KEYS = 10_000  # most emails (or addresses) remembered at once, per limiter


class FailureLimiter:
    """Allow `max_failures` failures per key within any `window` seconds."""

    def __init__(self, max_failures: int, window: float, clock: Callable[[], float] = time.monotonic):
        self.max_failures = max_failures
        self.window = window
        self._clock = clock
        self._lock = threading.Lock()
        self._failures: dict[str, deque[float]] = {}

    def _recent(self, key: str, now: float) -> deque[float] | None:
        """The failures of `key` still inside the window (oldest first), or None."""
        events = self._failures.get(key)
        if events is None:
            return None
        while events and events[0] <= now - self.window:
            events.popleft()
        if not events:
            del self._failures[key]
            return None
        return events

    def retry_after(self, key: str) -> int:
        """0 if `key` may try, otherwise the whole seconds to wait."""
        with self._lock:
            now = self._clock()
            events = self._recent(key, now)
            if events is None or len(events) < self.max_failures:
                return 0
            return max(1, math.ceil(events[0] + self.window - now))

    def record(self, key: str) -> None:
        with self._lock:
            now = self._clock()
            events = self._recent(key, now)
            if events is None:
                if len(self._failures) >= MAX_KEYS:
                    self._make_room(now)
                events = self._failures[key] = deque(maxlen=self.max_failures)
            events.append(now)

    def clear(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._failures.clear()

    def _make_room(self, now: float) -> None:
        """Called with the lock held when too many keys are remembered."""
        for key in list(self._failures):
            self._recent(key, now)  # drops keys whose failures have all expired
        while len(self._failures) >= MAX_KEYS:
            del self._failures[next(iter(self._failures))]  # the key seen longest ago


class LoginLimits:
    """The two limits on sign-in: failures per email, and failures per client address."""

    def __init__(
        self,
        max_per_email: int,
        max_per_ip: int,
        window: float,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.by_email = FailureLimiter(max_per_email, window, clock)
        self.by_ip = FailureLimiter(max_per_ip, window, clock)

    def retry_after(self, email: str, ip: str) -> int:
        """0 if this attempt may go ahead, otherwise how many seconds to wait."""
        return max(self.by_email.retry_after(email), self.by_ip.retry_after(ip))

    def record_failure(self, email: str, ip: str) -> None:
        self.by_email.record(email)
        self.by_ip.record(ip)

    def record_success(self, email: str) -> None:
        # Only the email is forgiven. Forgiving the address too would let someone
        # guess at other accounts and reset their count with a login of their own.
        self.by_email.clear(email)

    def reset(self) -> None:
        self.by_email.reset()
        self.by_ip.reset()
