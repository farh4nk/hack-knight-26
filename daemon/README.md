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

Run tests:
```bash
uv run pytest
```

## Presage

To use the real Presage integration via SmartSpectra, install Docker (e.g., on Arch):
```bash
sudo pacman -S docker && pkexec systemctl enable --now docker
```

Run the camera fanout script so both the Python daemon and Presage container can access the camera:
```bash
sudo scripts/camera_fanout.sh
```

Before running with Presage, it is recommended to run the preflight script:
```bash
scripts/preflight.sh --presage
```

Build the Presage bridge Docker image:
```bash
docker build -t cradleecho-presage-bridge presage_bridge
```

Run the daemon with Presage enabled (requires `PRESAGE_API_KEY`):
```bash
PRESAGE_API_KEY=your_api_key_here CRADLEECHO_SOURCE=presage CRADLEECHO_CAMERA=/dev/video10 CRADLEECHO_PRESAGE_CMD=presage_bridge/run_bridge.sh uv run uvicorn cradleecho.main:app --port 8000
```

## Configuration

The daemon is configured via environment variables or a `.env` file (parsed using `pydantic-settings`):

| Variable | Default | Description |
| --- | --- | --- |
| `PRESAGE_API_KEY` | None | API Key for Presage SmartSpectra backend. Required when source is `presage`. |
| `CRADLEECHO_CAMERA` | `0` | Camera device index (`0`) or V4L2 device path (`/dev/video10`). Falls back gracefully to synthetic 'NO CAMERA' feed if unavailable. |
| `CRADLEECHO_SOURCE` | `mock` | Vitals source: `mock` (realistic random walk) or `presage` (subadapter reading NDJSON stdout). |
| `CRADLEECHO_PRESAGE_CMD` | `python presage_bridge/fake_bridge.py` | Command to launch the Presage bridge binary/script. |
| `CRADLEECHO_HOST` | `0.0.0.0` | Host to bind the Uvicorn server to. |
| `CRADLEECHO_PORT` | `8000` | Port to bind the server to. |
| `CRADLEECHO_CORS_ORIGINS` | `*` | Comma-separated allowed CORS origins. |
| `CRADLEECHO_MIN_BRIGHTNESS` | `35` | Minimum mean brightness threshold for the lighting gate. |

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
  "motion_index": 0.72
}
```

Valid states: `ASLEEP | DROWSY | RESTLESS | AWAKE | SIGNAL_UNSTABLE`
