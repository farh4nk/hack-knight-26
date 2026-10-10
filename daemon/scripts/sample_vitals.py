#!/usr/bin/env python3
"""Sample the daemon's live readings and summarize them, to tune sleep-stage thresholds.

Run it twice against the running daemon, once while you sit still and once while you move
around, then compare the motion numbers with the defaults:

    uv run python scripts/sample_vitals.py --seconds 30 --label still
    uv run python scripts/sample_vitals.py --seconds 30 --label moving

Defaults: calm motion < 0.10, restless >= 0.20, awake >= 0.45; asleep breathing 22-40/min.
Override with CRADLEECHO_CALM_MOTION, CRADLEECHO_RESTLESS_MOTION, CRADLEECHO_AWAKE_MOTION,
CRADLEECHO_ASLEEP_BRPM_MIN / _MAX and CRADLEECHO_ASLEEP_HOLD_S.
"""

import argparse
import json
import statistics
import time
import urllib.request
from collections import Counter


def pct(values: list[float], p: float) -> float:
    return sorted(values)[max(0, int(len(values) * p) - 1)]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", default="http://localhost:8000/api/state")
    ap.add_argument("--seconds", type=float, default=30)
    ap.add_argument("--label", default="")
    args = ap.parse_args()

    rows = []
    end = time.time() + args.seconds
    while time.time() < end:
        try:
            d = json.load(urllib.request.urlopen(args.url, timeout=10))
            rows.append(d)
        except Exception:
            pass
        time.sleep(0.5)

    if not rows:
        raise SystemExit("No readings. Is the daemon running at " + args.url + "?")

    motion = [r["motion_index"] for r in rows]
    with_signal = [r for r in rows if r["vitals"]["confidence"] >= 0.4 and r["vitals"]["brpm"] > 0]
    print(f"== {args.label or 'sample'}: {len(rows)} readings over {args.seconds:.0f}s")
    print(f"motion   median={statistics.median(motion):.2f}  p90={pct(motion, .9):.2f}  max={max(motion):.2f}")
    if with_signal:
        brpm = [r["vitals"]["brpm"] for r in with_signal]
        bpm = [r["vitals"]["bpm"] for r in with_signal]
        print(f"breathing median={statistics.median(brpm):.1f}  min={min(brpm):.1f}  max={max(brpm):.1f}  /min  ({len(with_signal)} readings with signal)")
        print(f"heart    median={statistics.median(bpm):.0f} bpm")
    else:
        print("breathing: no readings with signal (is a face in view? is Presage running?)")
    print("states   " + ", ".join(f"{k}={v}" for k, v in Counter(r["state"] for r in rows).most_common()))


if __name__ == "__main__":
    main()
