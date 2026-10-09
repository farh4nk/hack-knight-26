# CradleEcho Edge Daemon

Edge daemon for CradleEcho baby monitor. Captures camera frames, computes motion index, consumes biometric vitals (breathing and pulse rates) via Presage SDK or mock source, classifies infant sleep states using a rolling state machine, and broadcasts real-time telemetry over WebSockets.

## Requirements

- Python >= 3.12
- [uv](https://docs.astral.sh/uv/) package manager

## Quickstart

Install dependencies:
```bash
uv sync
```

Run the daemon:
```bash
uv run python -m cradleecho
```
Open a browser on your phone on the same Wi-Fi network and navigate to `http://<LAN_IP>:8000` (the exact IP is printed in the logs on startup).

### macOS helper script

```bash
scripts/run_mac.sh                   # native, mock vitals, Mac webcam
scripts/run_mac.sh --facegate        # native, OpenCV face gate on (fake Presage bridge)
scripts/run_mac.sh docker            # Docker; webcam is streamed into the container
scripts/run_mac.sh docker --presage  # Docker with real Presage (PRESAGE_API_KEY in .env)
scripts/run_mac.sh docker --stamp   # also burn capture time into frames for latency testing
scripts/run_mac.sh stop
```

Measure end-to-end video latency with a real webcam (needs `--stamp`; prints PASS/FAIL):
```bash
uv run python scripts/measure_latency.py --seconds 20
```

Docker Desktop on macOS/Windows can't pass a camera device into a container, so Docker mode runs
`scripts/camera_publisher.py` on the host (MJPEG on :8090) and sets
`CRADLEECHO_CAMERA=http://host.docker.internal:8090/video`. `compose.mac.yaml` is the laptop
variant of `compose.yaml`; on the Pi keep using `compose.yaml` with direct `/dev/video0`.

Run tests:
```bash
uv run pytest
```

## Presage

Build and run via Docker Compose:
```bash
docker compose up --build
```

Mock run:
```bash
docker compose --profile mock up cradleecho-mock
```

This requires `PRESAGE_API_KEY` in `.env`. Set `VIDEO_GID` and `RENDER_GID` from `getent group video render` (names resolve inside the image, not on the host; compose defaults 44/105 suit Raspberry Pi OS but verify).

Presage must run at ~30 fps (`CRADLEECHO_PRESAGE_FPS` default 30; below ~15 fps the SDK fails with `kProcessingFailed`).

Framing tips:
- One face, centered at eye level
- Upper chest visible
- Well lit, still
- SDK validation hints such as `kChestNotVisible` / `kFaceTooLow` appear in logs and state stays `SIGNAL_UNSTABLE` until it is happy.

## Configuration

The daemon is configured via environment variables or a `.env` file (parsed using `pydantic-settings`):

| Variable | Default | Description |
| --- | --- | --- |
| `PRESAGE_API_KEY` | None | API Key for Presage SmartSpectra backend. Required when source is `presage`. |
| `CRADLEECHO_CAMERA` | `0` | Camera device index (`0`) or V4L2 device path (`/dev/video0`). Falls back gracefully to synthetic 'NO CAMERA' feed if unavailable. |
| `CRADLEECHO_SOURCE` | `mock` | Vitals source: `mock` (realistic random walk) or `presage` (subadapter reading NDJSON stdout). |
| `CRADLEECHO_PRESAGE_CMD` | `python presage_bridge/fake_bridge.py` | Command to launch the Presage bridge binary/script. The docker image sets `/opt/bridge/bridge --stdin 640x480`. |
| `CRADLEECHO_PRESAGE_FPS` | `30` | Expected framerate for Presage SDK (below ~15 fps causes `kProcessingFailed`). |
| `CRADLEECHO_HOST` | `0.0.0.0` | Host to bind the Uvicorn server to. |
| `CRADLEECHO_PORT` | `8000` | Port to bind the server to. |
| `CRADLEECHO_CORS_ORIGINS` | `*` | Comma-separated allowed CORS origins. |
| `CRADLEECHO_MIN_BRIGHTNESS` | `35` | Minimum mean brightness threshold for the lighting gate. |
| `CRADLEECHO_FACE_GATE` | `True` | Enable the Haar cascade face gate to suspend Presage SDK billing/CPU when nobody is in frame. |
| `CRADLEECHO_GATE_CHEST_ROOM` | `1.75` | Required chest room under face, as multiple of face height. |
| `CRADLEECHO_GATE_MIN_FACE` | `0.15` | Minimum face height as fraction of frame height. |

### Face gate

When `CRADLEECHO_FACE_GATE` is enabled, an OpenCV Haar cascade face detector analyzes frames before sending them to the Presage bridge. The bridge is spawned only when a valid face (centered, appropriate size, visible chest room) is detected continuously for 2 seconds. When the face is lost for 10 seconds, the bridge process is terminated to save CPU and credits, and the system reports `SIGNAL_UNSTABLE`.

## Endpoints

- `GET /healthz`: Health check returning `{"status": "ok", "source": "mock"|"presage"}`.
- `GET /video_feed`: MJPEG stream (`multipart/x-mixed-replace`) backed by a single shared capture thread.
- `GET /api/state`: Returns the latest telemetry payload.
- `POST /api/simulate-restless`: Stage demo trigger forcing `RESTLESS` state for 15 seconds (optional JSON: `{"seconds": n}`).
- `POST /api/simulate-unstable`: Stage demo trigger forcing `SIGNAL_UNSTABLE` state for 15 seconds (optional JSON: `{"seconds": n}`).
- `WS /ws/telemetry`: 2 Hz WebSocket stream broadcasting the standard AGENTS.md telemetry payload.

### Telemetry Payload Schema

```json
{
  "timestamp": "2026-10-09T14:30:00Z",
  "state": "RESTLESS",
  "vitals": {
    "brpm": 34.2,
    "bpm": 118.0,
    "confidence": 0.88
  },
  "motion_index": 0.72,
  "camera": {
    "live": true,
    "gate": "OPEN",
    "framing": "OK",
    "sdk_code": "kFaceLow",
    "sdk_hint": "Move up, or tilt the camera down."
  }
}
```

Valid states: `ASLEEP | DROWSY | RESTLESS | AWAKE | SIGNAL_UNSTABLE`

*Note: The `camera` object is additive/backward compatible, and `state` valid values remain unchanged.*
**Camera fields:**
- `live` (bool): `true` when capturing real frames, `false` if synthetic fallback
- `gate` (string): `OPEN`, `CLOSED`, or `DISABLED`
- `framing` (string): `OK`, `NO_FACE`, `MULTIPLE_FACES`, `TOO_SMALL`, `OFF_CENTER`, `NO_CHEST_ROOM`, or `UNKNOWN`
- `sdk_code` (string | null): latest Presage validation error code (e.g. `kFaceTooLow`), or `null`
- `sdk_hint` (string | null): human-readable Presage fix instruction, or `null`

## Raspberry Pi 4

Pi OS 64-bit + Docker:
1. Copy `.env`
2. Run `docker compose up -d`
3. Open `http://<pi-ip>:8000/video_feed`

Build the arm64 image on the laptop:
```bash
docker run --privileged --rm tonistiigi/binfmt --install arm64
docker buildx build --platform linux/arm64 -t cradleecho-daemon .
docker save cradleecho-daemon | ssh pi docker load
```
Note: arm64 is NOT yet tested.
