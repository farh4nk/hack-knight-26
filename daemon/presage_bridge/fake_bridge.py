#!/usr/bin/env python3
"""Fake Presage (SmartSpectra) bridge emitting NDJSON to stdout."""

import json
import random
import signal
import sys
import threading
import time


def start_stdin_reader(width: int, height: int, counter: list[int]) -> None:
    """Drain W*H*3-byte raw frames from stdin, counting them (mirrors bridge --stdin)."""
    frame_bytes = width * height * 3

    def run() -> None:
        while True:
            data = sys.stdin.buffer.read(frame_bytes)
            if len(data) < frame_bytes:
                return
            counter[0] += 1

    threading.Thread(target=run, daemon=True).start()


def main() -> None:
    running = True
    frames = [0]
    stdin_mode = "--stdin" in sys.argv
    if stdin_mode:
        w, h = sys.argv[sys.argv.index("--stdin") + 1].split("x")
        start_stdin_reader(int(w), int(h), frames)

    def handle_signal(sig, frame):
        nonlocal running
        running = False
        sys.stderr.write(f"fake_bridge: caught signal {sig}, exiting\n")
        sys.stderr.flush()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    sys.stderr.write("fake_bridge: started emitting vitals NDJSON to stdout\n")
    sys.stderr.flush()

    brpm = 24.0
    bpm = 119.0
    conf = 0.92
    motion = 0.12

    try:
        while running:
            # Subtle random walk around normal infant vitals
            brpm += random.uniform(-0.3, 0.3)
            brpm = max(21.0, min(27.0, brpm))

            bpm += random.uniform(-0.5, 0.5)
            bpm = max(115.0, min(125.0, bpm))

            conf += random.uniform(-0.02, 0.02)
            conf = max(0.85, min(0.96, conf))

            motion += random.uniform(-0.02, 0.02)
            motion = max(0.05, min(0.20, motion))

            if stdin_mode and frames[0] == 0:
                time.sleep(0.1)
                continue

            payload = {
                "t": time.time(),
                "brpm": round(brpm, 2),
                # In stdin mode bpm reports frames received, so tests can observe the pipe.
                "bpm": float(frames[0]) if stdin_mode else round(bpm, 2),
                "confidence": round(conf, 2),
                "motion_index": round(motion, 2),
            }

            line = json.dumps(payload) + "\n"
            sys.stdout.write(line)
            sys.stdout.flush()

            time.sleep(0.5)
    except (BrokenPipeError, KeyboardInterrupt):
        pass
    finally:
        sys.stderr.write("fake_bridge: terminated\n")
        sys.stderr.flush()


if __name__ == "__main__":
    main()
