import threading
import time


class TokenBucket:
    """Rate limiter with token bucket algorithm.

    Thread-safe via lock. Note that `wait_time()` computes the estimated
    wait without consuming a token — a concurrent `consume()` call between
    `wait_time()` and the subsequent `consume()` may change the actual wait.
    """

    def __init__(self, tokens_per_second: float, max_burst: float) -> None:
        self._rate = tokens_per_second
        self._max = max_burst
        self._tokens = max_burst
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def consume(self, tokens: float = 1.0) -> bool:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            self._tokens = min(self._max, self._tokens + elapsed * self._rate)
            self._last = now
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    def wait_time(self) -> float:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            self._tokens = min(self._max, self._tokens + elapsed * self._rate)
            self._last = now
            if self._tokens >= 1.0:
                return 0.0
            return (1.0 - self._tokens) / self._rate
