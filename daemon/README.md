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
uv run uvicorn cradleecho.main:app --host 0.0.0.0 --port 8000
```

Run tests:
```bash
uv run pytest
```

## Configuration

The daemon is configured via environment variables:

| Variable | Default | Description |
| --- | --- | --- |
| `CRADLEECHO_CAMERA` | `0` | Camera device index (`0`) or V4L2 device path (`/dev/video10`). Falls back gracefully to synthetic 'NO CAMERA' feed if unavailable. |
| `CRADLEECHO_SOURCE` | `mock` | Vitals source: `mock` (realistic random walk) or `presage` (subadapter reading NDJSON stdout). |
| `CRADLEECHO_PRESAGE_CMD` | `python presage_bridge/fake_bridge.py` | Command to launch the Presage bridge binary/script. |

## Endpoints

- `GET /healthz`: Health check returning `{"status": "ok"}`.
- `GET /video_feed`: MJPEG stream (`multipart/x-mixed-replace`) backed by a single shared capture thread.
- `GET /api/state`: Returns the latest telemetry payload.
- `POST /api/simulate-restless`: Stage demo trigger forcing `RESTLESS` state for 15 seconds (optional JSON: `{"seconds": n}`).
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
