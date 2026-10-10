"""Optional pipeline counters (CRADLEECHO_DIAG=1): where do frames and vitals get lost?

Each stage calls `count(name)` / `timed(name, seconds)`; a background thread logs a summary every
`INTERVAL_S`. Disabled, every call is a cheap early return.
"""

import logging
import os
import threading
import time
from collections import defaultdict

logger = logging.getLogger("cradleecho.diag")

ENABLED = os.environ.get("CRADLEECHO_DIAG", "").lower() in ("1", "true", "yes")
INTERVAL_S = 5.0

_lock = threading.Lock()
_counts: dict[str, int] = defaultdict(int)
_time_sum: dict[str, float] = defaultdict(float)
_values: dict[str, str] = {}
_started = False


def count(name: str, n: int = 1) -> None:
    if ENABLED:
        with _lock:
            _counts[name] += n


def timed(name: str, seconds: float) -> None:
    if ENABLED:
        with _lock:
            _counts[name] += 1
            _time_sum[name] += seconds


def value(name: str, text: str) -> None:
    if ENABLED:
        with _lock:
            _values[name] = text


def _report_loop() -> None:
    last = time.monotonic()
    while True:
        time.sleep(INTERVAL_S)
        now = time.monotonic()
        dt = now - last
        last = now
        with _lock:
            counts = dict(_counts)
            sums = dict(_time_sum)
            values = dict(_values)
            _counts.clear()
            _time_sum.clear()
        parts = []
        for name in sorted(counts):
            n = counts[name]
            if name in sums:
                parts.append(f"{name}={n / dt:.1f}/s avg {1000 * sums[name] / n:.1f}ms")
            else:
                parts.append(f"{name}={n / dt:.1f}/s")
        parts.extend(f"{k}={v}" for k, v in sorted(values.items()))
        logger.warning("DIAG %s", " ".join(parts) if parts else "(no activity)")


def start() -> None:
    global _started
    if ENABLED and not _started:
        _started = True
        threading.Thread(target=_report_loop, name="DiagThread", daemon=True).start()
        logger.warning("DIAG enabled: logging pipeline rates every %.0fs", INTERVAL_S)
