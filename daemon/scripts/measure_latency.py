#!/usr/bin/env python3
"""Measure end-to-end video latency of the daemon's /video_feed.

Needs frames stamped by the publisher:  scripts/run_mac.sh docker --stamp
(or: python scripts/camera_publisher.py --stamp). Runs on the host, so clocks match.

Reports capture-read -> daemon output delay: the part software controls. Webcam sensor +
USB (typically 30-100 ms) happens before the read and is not included.

Usage: uv run python scripts/measure_latency.py [--url URL] [--seconds 20]
"""

import argparse
import statistics
import time
import urllib.request

import cv2
import numpy as np

BITS, BLOCK = 40, 16


def decode_stamp(gray: np.ndarray) -> int:
    bits = [1 if gray[BLOCK // 2, i * BLOCK + BLOCK // 2] > 127 else 0 for i in range(BITS)]
    return sum(b << (BITS - 1 - i) for i, b in enumerate(bits))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", default="http://localhost:8000/video_feed")
    ap.add_argument("--seconds", type=float, default=20)
    args = ap.parse_args()

    stream = urllib.request.urlopen(args.url, timeout=10)
    buf = b""
    samples: list[tuple[float, int]] = []  # (seconds since start, latency ms)
    start = time.time()
    mask = (1 << BITS) - 1
    while time.time() - start < args.seconds:
        buf += stream.read(65536)
        while True:
            a = buf.find(b"\xff\xd8")
            b = buf.find(b"\xff\xd9", a + 2)
            if a < 0 or b < 0:
                break
            jpg, buf = buf[a : b + 2], buf[b + 2 :]
            img = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_GRAYSCALE)
            if img is None or img.shape[1] < BITS * BLOCK:
                continue
            delay = ((int(time.time() * 1000) & mask) - decode_stamp(img)) & mask
            if delay < 60_000:  # anything larger is an unstamped/garbled frame
                samples.append((time.time() - start, delay))

    if not samples:
        raise SystemExit("No stamped frames decoded. Start the stack with --stamp.")

    vals = [d for _, d in samples]
    third = max(1, len(vals) // 3)
    early, late = statistics.median(vals[:third]), statistics.median(vals[-third:])
    p95 = sorted(vals)[int(len(vals) * 0.95) - 1]
    print(f"frames: {len(vals)}  ({len(vals) / args.seconds:.1f} fps)")
    print(f"latency ms: median={int(statistics.median(vals))}  p95={p95}  max={max(vals)}")
    print(f"first third median={int(early)} ms, last third median={int(late)} ms")
    verdict = "PASS" if statistics.median(vals) < 300 and late - early < 150 else "FAIL"
    print(f"{verdict}: expect median < 300 ms and no growth over the run (the old bug grew to seconds)")


if __name__ == "__main__":
    main()
