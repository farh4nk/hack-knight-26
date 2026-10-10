# Web frontend (Dev 2)

Next.js 16 + Tailwind 4. The parent's monitoring UI: live stream, sleep-state badge, vitals sparklines, demo trigger.

## Run

```bash
cd web
npm install
cp .env.example .env.local   # then edit
npm run dev                  # http://localhost:3000
```

| Env var | Default | Meaning |
|---|---|---|
| `NEXT_PUBLIC_DAEMON_URL` | unset | Dev 1's daemon. Unset = the host that served the page, port 8000, so the UI works from any device (a laptop opening `http://<pi>:3000` reaches the Pi's daemon, not its own). Set it only to point somewhere else |
| `NEXT_PUBLIC_ANALYTICS_URL` | unset | Dev 4's analytics API. Unset = the page's host, port 8001 |
| `NEXT_PUBLIC_MOCK` | `0` | `1` = fake telemetry generated in the browser, no daemon needed |

`NEXT_PUBLIC_*` values are baked in at build time. Restart `npm run dev` after changing them.

On the Pi the UI ships as a Docker image; see [docs/pi-setup.md](../docs/pi-setup.md).

## Daemon endpoints used

- `GET  /video_feed`: MJPEG stream
- `GET  /video_feed/debug`: same stream with the daemon's face-gate and vitals overlay (the "Debug overlay" toggle under the feed)
- `WS   /ws/telemetry`: telemetry JSON at 2 Hz (see `lib/types.ts`). The optional `camera` object drives the status chips under the feed, and its `sdk_hint` replaces the generic text on the Signal Unstable badge
- `POST /api/simulate-restless`: forces RESTLESS for 15s

## Reading telemetry from your own component (Dev 3, Dev 4)

```tsx
"use client";
import { useTelemetry } from "@/context/TelemetryProvider";

const { latest, history, connected, stale, simulateRestless } = useTelemetry();
// latest?.state === "RESTLESS"
```

The provider is already mounted in `app/layout.tsx`, so any client component can call the hook.
