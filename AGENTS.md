# CradleEcho

## Working pitch

CradleEcho is a baby monitor that does more than show a live crib feed. It interprets sleep quality in real time, surfacing breathing and heart-rate signals, and can soothe a restless baby in the parent’s own voice before the parent has to get up.

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
  "motion_index": 0.72
}
```

Valid states: `ASLEEP | DROWSY | RESTLESS | AWAKE | SIGNAL_UNSTABLE`

## Team responsibilities

### Dev 1: Computer vision & edge daemon (Python / FastAPI)

Deliverable: a local service that streams video and emits parsed biometric states.

- [x] Task 1.1 — Video capture & stream: set up a FastAPI service with an MJPEG streaming endpoint at `/video_feed` using OpenCV (`cv2.VideoCapture(0)`).
- [ ] Task 1.2 — Presage integration: connect the Presage SDK (SmartSpectra) to pull breathing rate (BrPM), pulse rate (BPM), and tracking confidence. Fallback: write a mock telemetry generator first so Dev 2 is not blocked.
- [x] Task 1.3 — Sleep state classifier: implement the rolling state machine:
  - If confidence < 0.40 => `SIGNAL_UNSTABLE`
  - If BrPM is stable (20–30) with low motion => `ASLEEP`
  - If BrPM spikes by > 25% or motion is high => `RESTLESS`
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
- [ ] Task 2.5 — Safety UI: place the required disclaimer in the footer: “CradleEcho is an informational wellness monitor, not a medical or SIDS-prevention device.”
- [ ] Task 2.6 — Stage demo controls: add a hidden or prominent “Trigger Test Restlessness” button that hits Dev 1’s mock endpoint.

### Dev 3: Audio pipeline & auto-soothe engine (ElevenLabs + Web Audio)

Deliverable: voice-cloning setup and the automated multi-track playback loop.

- [ ] Task 3.1 — Instant Voice Clone (IVC) onboarding: build a 10-second browser mic recorder component. On completion, call ElevenLabs:
  `POST https://api.elevenlabs.io/v1/voices/add` with the audio blob to register the parent’s voice and retrieve `voice_id`.
- [ ] Task 3.2 — Pre-render soothing audio snippets: send text prompts to `POST /v1/text-to-speech/{voice_id}` to generate three calming variations:
  - “Shh, you’re safe, go back to sleep Maya.”
  - “Mommy and daddy are right here, sweet dreams.”
  - “Everything is okay, close your eyes.”
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

  Output: a clean three-bullet report for the parent, e.g. “Maya slept 7.8 hours. Auto-soothe intervened twice, settling restlessness in under 45 seconds each time.”
- [ ] Task 4.4 — Domain & hosting: register the project domain via GoDaddy and configure DNS to point to the Vercel or Render deployment.

## Definition of done

The project is successful when:

- the live stream loads on a mobile browser,
- the telemetry stream updates in real time,
- the sleep-state badge changes correctly,
- auto-soothe triggers only when needed and fades cleanly,
- the dashboard shows trend data and the night summary,
- the demo can run reliably without a real infant on stage.
