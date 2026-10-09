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
| `NEXT_PUBLIC_DAEMON_URL` | `http://localhost:8000` | Dev 1's daemon. Use `http://<pi-ip>:8000` when it runs on the Pi |
| `NEXT_PUBLIC_MOCK` | `0` | `1` = fake telemetry generated in the browser, no daemon needed |

`NEXT_PUBLIC_*` values are baked in at build time. Restart `npm run dev` after changing them.

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
