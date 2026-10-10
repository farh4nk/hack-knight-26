# Cribby

## Working pitch

Cribby is a baby monitor that does more than show a live crib feed. It interprets sleep quality in real time, surfacing breathing and heart-rate signals, and can soothe a restless baby in the parent’s own voice before the parent has to get up.

## Product vision

- Live camera stream to a web UI, viewable from a phone
- Sleep-state intelligence powered by Presage
- Real-time parent-facing dashboard with sleep status and key vitals
- Local Python daemon for capture, inference, and WebSocket telemetry
- Auto-soothe flow driven by voice + ambient audio

## Core features

- Live camera stream to a web UI: low-latency feed (WebRTC or MJPEG for the fastest path)
- Sleep detection with Presage: derive state from breathing and heart rate, then display it as a badge on the feed
- Web app first: stream, current sleep state, and basic wake alerts
- Local Python daemon: captures the feed, runs the sleep-state logic, and pushes video and telemetry to the app over WebSocket

## Priority features

- Sleep dashboard
  - Timeline of sleep and wake states
  - Total sleep time, longest uninterrupted stretch, and number of wake-ups
  - Breathing-rate trend over time
- ElevenLabs voice cloning
  - Parent records a short sample during onboarding
  - “Talk to baby” button that speaks typed text in the parent’s voice
  - Pre-generated soothing phrases for instant playback
- Soothing sounds and music
  - White noise, rain, heartbeat, and lullabies
  - Volume control and sleep-timer support
- Auto-soothe mode
  - Restlessness detected via Presage triggers a cloned-voice phrase or soundscape
  - Volume fades out once the baby falls asleep again
  - Parent gets a visible notification when the system intervenes

Auto-soothe is the demo centerpiece because it combines Presage, ElevenLabs, and the audio pipeline into one visible loop.

## Nice-to-haves

- Two-way audio for a parent to speak live through the monitor
- Cry detection to reduce false alarms
- Night vision or low-light enhancement
- Multi-caregiver view-only sharing
- Room sensors for temperature and humidity overlay
- AI-written morning recap of the night
- PWA install for a more native app feel
- Privacy-first mode with local-only processing and no default video recording

## Sponsor tracks

| Track | Role in the stack |
| --- | --- |
| Presage | Breathing and heart-rate signals drive the sleep state and auto-soothe trigger |
| ElevenLabs | Cloned parent voice for soothing phrases and “talk to baby” |
| Health Hack | Helps exhausted parents sleep while still understanding their baby’s state |
| Tiger Data | Sleep timeline as time-series telemetry for state, breathing rate, and soothe events |
| Gemini | Morning recap of the night, if time allows |
| GoDaddy | Domain registration and deployment support |

## Safety rails

- Not a medical device. State this once on screen and once in the pitch. Do not claim SIDS prevention or diagnosis.
- Alerts should describe what was observed, e.g. “breathing signal lost,” never “your baby is in danger.”
- Signal-quality gate: if the face or chest is not visible or the lighting is poor, show “signal unstable” instead of guessing.
- Process locally where possible. Only derived numbers are stored, and video is not recorded by default.
- Auto-soothe is dismissible, with a visible off switch and a cap on how often it can trigger.

## Demo script (about 2 minutes)

1. Hook: tell the real story of a tired parent hearing “is that a cry or just noise?” at 3 a.m.
2. Live feed: show the stream with the sleep badge on a phone.
3. Setup moment: record a 10-second voice sample live.
4. Auto-soothe: hit “simulate restless.” The badge flips to restless, the cloned voice plays, and the soundscape fades in.
5. Settle: the state returns to asleep, audio fades out, and the parent receives a notification.
6. Dashboard: show the night’s timeline and sleep summary.

## Shared data contract

All four developers should build against this standard WebSocket telemetry payload:

```json
{
  "timestamp": "2026-10-09T14:30:00Z",
  "state": "RESTLESS",
  "vitals": {
    "brpm": 34.2,
    "bpm": 118,
    "confidence": 0.88
  },
  "motion_index": 0.72,
  "camera": {
    "live": true,
    "gate": "OPEN",
    "framing": "OK",
    "sdk_code": "kFaceTooLow",
    "sdk_hint": "Move up, or tilt the camera down.",
    "enabled": true
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
- `night_vision` (string): `OFF`, `AUTO`, or `ON` — configured night vision mode
- `enhancing` (bool): `true` when low-light enhancement is currently applied to the video feed
- `enabled` (bool, optional): `false` when the user switched the camera off (`POST /api/camera`); vitals are zeroed, `state` is `SIGNAL_UNSTABLE`, and consumers should not record the reading

## Project status (updated 2026-10-10)

The task checkboxes below are the original plan and are not maintained. Current state:
- Built and merged: web UI, daemon (capture, face gate, classifier, telemetry, camera switch), voice clone + auto-soothe, ingestion worker and Gemini recap code, Pi deployment.
- **Presage on a Pi 4 is not reliable**: the bridge gets 20-25 fps (needs 25). Run Presage on a laptop that reads the Pi's stream (29 fps measured). See `docs/presage-compute.md`.
- Never run end to end on real hardware: database ingestion, the Gemini recap against live data, auto-soothe with a real voice clone on the Pi speaker.
- Open PRs: #20 (Presage reliability), #18 (two-way audio, night vision, PWA; conflicts), #19 (LAN HTTPS, stacked on #18).

### Realistic scope for the deadline (Sunday 12 PM)

Aim for: a nursery camera on the Pi plus a laptop that shows the live feed, sleep state, auto-soothe and the morning recap, with the laptop computing the vitals. Do not aim for "everything runs on one Pi" (a Pi 4 is measurably too slow; a Pi 5 is untested).

- **Tier 1, core demo (high confidence):** live camera stream to the web UI over Tailscale; sleep state from vitals; sleep badge flips on "Trigger Test Restlessness", cloned voice plays and the soundscape fades in; state settles, audio fades out, parent is notified; dashboard timeline; Gemini morning recap. Presage vitals for the live parts, with simulated vitals as the fallback.
- **Tier 2, real vitals that stay smooth (about 60%):** Presage on a Mac reading the Pi's stream (29 fps measured) with framing good enough that Presage stops asking for the chest or "hold still", and breathing and heart rate holding for several minutes. Depends on light, distance and sitting still.
- **Tier 3, stretch (low):** two-way audio, night vision, PWA (PR #18, untested on hardware, conflicts with `main`); LAN HTTPS (PR #19, overlaps with Tailscale); a single-Pi product.

Schedule (Saturday = Oct 10):

| When | What | Who |
|---|---|---|
| Sat early | Merge #20. Run Mac Presage 10 min with the camera pulled back; confirm BPM and breathing hold. | Dev 2 |
| Sat morning | Tiger Data connection string, run the ingestion worker, confirm rows appear; run the Gemini recap on real data. | Dev 4 |
| Sat midday | Auto-soothe with the real voice clone and the Pi speaker; UI hookup for the Mac setup. | Dev 2, Dev 3 |
| Sat afternoon | Decide on PR #18 (rebase and hardware-test, or park it) and #19. | Team |
| Sat evening | One full run (camera, vitals, database, recap, soothe); rehearse the 2-minute demo twice. | Everyone |
| Sun morning | No new features. Fix only what rehearsal breaks. Prepare the "why a Pi?" answer. | Everyone |

Rules:
1. Tier 1 first; no Tier 3 work until a full run works.
2. Cutoff for real vitals: Saturday 8 PM. If they are not stable by then, demo with simulated vitals plus a short live moment of the real camera.
3. Anything not working on the Pi by Sunday morning stays out of the demo.
4. Do not overclaim: say what was measured and what was not tested.

### Why a Pi? (expected judge question)

The Pi is the nursery unit: always-on camera, speaker for the cloned-voice and lullabies, low power, face-gated privacy, no video recorded. Presage's vitals need more compute than a Pi 4 has (measured: 20-25 of the 25 fps the SDK requires; 29 fps when Presage runs on a Mac), so vitals run on a home hub. A Pi 5 should fit it in one box (untested). Do not claim everything runs on the Pi or that a Pi 5 definitely works.

## Team responsibilities

### Dev 1: Computer vision & edge daemon (Python / FastAPI)

Deliverable: a local service that streams video and emits parsed biometric states.

- [x] Task 1.1 — Video capture & stream: set up a FastAPI service with an MJPEG streaming endpoint at `/video_feed` using OpenCV (`cv2.VideoCapture(0)`).
- [x] Task 1.2 — Presage integration: connect the Presage SDK (SmartSpectra) to pull breathing rate (BrPM), pulse rate (BPM), and tracking confidence. Fallback: write a mock telemetry generator first so Dev 2 is not blocked.
- [x] Task 1.3 — Sleep state classifier: implement the rolling state machine:
  - If confidence < 0.40 => `SIGNAL_UNSTABLE`
  - `AWAKE` is the default: clear movement, or breathing outside the sleeping range (22–40/min)
  - `ASLEEP` needs calm movement AND in-range breathing held for 20 s (until then `DROWSY`)
  - `RESTLESS` = a sleeper stirring: moderate movement with in-range breathing, or breathing > 25% above the baby's sleeping baseline
  - No breathing estimate yet (Presage warm-up) => `SIGNAL_UNSTABLE`
  - All thresholds are `CRADLEECHO_*` settings (see `daemon/README.md`)
- [x] Task 1.4 — Stage demo trigger: create a manual REST endpoint, `POST /api/simulate-restless`, that forces the state machine to `RESTLESS` for 15 seconds.
- [x] Task 1.5 — WebSocket server: broadcast the telemetry JSON over `ws://localhost:8000/ws/telemetry` at 2 Hz.
- [ ] Task 1.6 - Dockerize the daemon and package it with LinuxKit for usage on a raspberry pi

### Dev 2: Frontend & real-time dashboard (Next.js / Tailwind)

Deliverable: the parent-facing mobile-first monitoring UI.

- [ ] Task 2.1 — Stream component: build a responsive card embedding `<img src="http://localhost:8000/video_feed" />` so it renders quickly on both laptop and mobile.
- [ ] Task 2.2 — WebSocket client: connect to the telemetry WebSocket and store the state in React context.
- [ ] Task 2.3 — Live state badge:
  - Green: `Asleep`
  - Yellow/pulsing: `Restless - Auto-Soothe Primed`
  - Red: `Awake`
  - Grey: `Signal Unstable — Adjust Crib Lighting`
- [ ] Task 2.4 — Live vitals gauges: render cards for breathing rate (BrPM) and heart rate (BPM) with simple sparkline charts.
- [ ] Task 2.5 — Safety UI: place the required disclaimer in the footer: “Cribby is an informational wellness monitor, not a medical or SIDS-prevention device.”
- [ ] Task 2.6 — Stage demo controls: add a hidden or prominent “Trigger Test Restlessness” button that hits Dev 1’s mock endpoint.

### Dev 3: Audio pipeline & auto-soothe engine (ElevenLabs + Web Audio)

Deliverable: voice-cloning setup and the automated multi-track playback loop.

- [ ] Task 3.1 — Instant Voice Clone (IVC) onboarding: build a 10-second browser mic recorder component. On completion, call ElevenLabs:
  `POST https://api.elevenlabs.io/v1/voices/add` with the audio blob to register the parent’s voice and retrieve `voice_id`.
- [ ] Task 3.2 — Pre-render soothing audio snippets: send text prompts to `POST /v1/text-to-speech/{voice_id}` to generate three short phrases, spoken in a soft, gentle voice:
  - “Shhh”
  - “Go to sleep”
  - “Good night”
- [ ] Task 3.3 — Auto-soothe orchestrator: subscribe to the telemetry stream. When `state === "RESTLESS"` for 4 seconds:
  - trigger an ambient lullaby/heartbeat track using HTML5 Audio
  - overlay the ElevenLabs snippet at 70% volume
  - when the state returns to `ASLEEP`, smoothly ramp the volume to 0 over 8 seconds
- [ ] Task 3.4 — Auto-soothe safeguards: implement a 10-minute cooldown lockout so auto-soothe does not repeat endlessly if the baby is truly awake and crying, plus an instant “Mute / Stop Soothe” UI control.

### Dev 4: Database, Gemini summary & pitch assets (Tiger Data + Gemini)

Deliverable: time-series telemetry storage, the AI morning briefing, and deployment.

- [ ] Task 4.1 — Tiger Data PostgreSQL setup: create a Tiger Data / Timescale database and run table migrations:

```sql
CREATE TABLE baby_vitals (
    time TIMESTAMPTZ NOT NULL,
    state VARCHAR(20) NOT NULL,
    breathing_rate DOUBLE PRECISION,
    heart_rate DOUBLE PRECISION,
    confidence DOUBLE PRECISION
);

CREATE TABLE soothe_events (
    id SERIAL PRIMARY KEY,
    triggered_at TIMESTAMPTZ NOT NULL,
    resolved_at TIMESTAMPTZ,
    voice_snippet_used TEXT,
    was_successful BOOLEAN
);
```

- [ ] Task 4.2 — Telemetry ingestion worker: write a background script or endpoint that takes incoming WebSocket packets and inserts batched rows into `baby_vitals` every 5 seconds.
- [ ] Task 4.3 — Gemini 1.5 morning recap: build a backend route, `/api/nightly-summary`, that fetches the night’s metrics from Tiger Data and prompts Gemini with:
  - total sleep time
  - count of restlessness spikes
  - average BrPM
  - soothe events count and resolution durations

  Output: a clean three-bullet report for the parent, e.g. “[Name] slept 7.8 hours. Auto-soothe intervened twice, settling restlessness in under 45 seconds each time.”
- [ ] Task 4.4 — Domain & hosting: register the project domain via GoDaddy and configure DNS to point to the Vercel or Render deployment.

## Definition of done

The project is successful when:

- the live stream loads on a mobile browser,
- the telemetry stream updates in real time,
- the sleep-state badge changes correctly,
- auto-soothe triggers only when needed and fades cleanly,
- the dashboard shows trend data and the night summary,
- the demo can run reliably without a real infant on stage.
