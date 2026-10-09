# CradleEcho — Backend & Analytics Engine (Dev 4)

> **CradleEcho** is an intelligent infant wellness monitor that interprets sleep quality in real time, surfaces breathing and pulse rates, and soothes a restless baby in the parent's cloned voice before the parent has to get up.

This module houses the **Tiger Data (TimescaleDB)** time-series storage, the **WebSocket Telemetry Ingestion Worker**, and the **Google Gemini Morning Recap Engine**.

---

## 🛠️ Architecture Overview

```
 [Dev 1: Computer Vision & Edge Daemon]
        │
        │ WebSocket Telemetry (2 Hz)
        ▼
 ┌───────────────────────────────────────────────┐
 │  Telemetry Ingestion Worker                   │
 │  (backend/services/ingestion_worker.py)       │
 └──────────────────────┬────────────────────────┘
                        │ Batched Inserts (Every 5s)
                        ▼
 ┌───────────────────────────────────────────────┐
 │  Tiger Data / TimescaleDB                     │
 │  - baby_vitals (Time-series Hypertable)       │
 │  - soothe_events (Interventions)              │
 └───────┬───────────────────────────────┬───────┘
         │                               │
         │ SQL Aggregations              │ SQL Queries
         ▼                               ▼
 ┌─────────────────────────────┐ ┌─────────────────────────────┐
 │  Gemini Morning Briefing    │ │  FastAPI Analytics Server   │
 │  (gemini_summary.py)        │ │  (backend/api/app.py)       │
 └──────────────┬──────────────┘ └──────────────┬──────────────┘
                │                               │
                │ /api/nightly-summary          │ /api/sleep-timeline
                │                               │ /api/vitals-trend
                ▼                               ▼
       [Dev 2: Next.js Mobile-First Dashboard UI]
       [Dev 3: Auto-Soothe Audio Pipeline Integration]
```

---

## 📋 Prerequisites & Setup

### 1. Clone & Switch Branch
```bash
git checkout dev4/database
```

### 2. Install Dependencies
Using your active conda or virtual environment:
```bash
pip install -r backend/requirements.txt
```

### 3. Environment Variables (`.env`)
Create a `.env` file in the project root:
```bash
cp .env.example .env
```

Configure your credentials inside `.env`:
```env
# Tiger Data / TimescaleDB PostgreSQL URI
DATABASE_URL=postgresql://tsdbadmin:<password>@<host>:<port>/tsdb?sslmode=require

# Google Gemini API Key (Get free key from https://aistudio.google.com/)
GEMINI_API_KEY=your_gemini_api_key_here

# Dev 1 Telemetry WebSocket Endpoint (Task 4.2)
TELEMETRY_WS_URL=ws://localhost:8000/ws/telemetry

# Ingestion Batch Interval (seconds)
INGESTION_INTERVAL_SECONDS=5
```

> **Note on Networks**: When connecting to Timescale Cloud from restricted campus or venue Wi-Fi networks (which often block port `30148`), enable **Cloudflare WARP** or a personal mobile hotspot.

---

## 🚀 Commands & Execution

### 1. Database Migrations (Tiger Data / Timescale)
Creates `baby_vitals` (with hypertable optimization) and `soothe_events`:
```bash
python -m backend.db.migrate
```

### 2. Seed Realistic 8-Hour Demo Data
Populates Tiger Data with an 8-hour sleep session (5,760+ vitals rows, normal baseline, 2 restlessness episodes, and 2 auto-soothe events) so Dev 2's dashboard has instant historical data:
```bash
python -m backend.scripts.seed_demo_data
```

### 3. Start the Analytics & Summary API Server
Runs FastAPI on port `8001` with CORS enabled:
```bash
uvicorn backend.api.app:app --host 0.0.0.0 --port 8001 --reload
```
Interactive Swagger docs: `http://localhost:8001/docs`

### 4. Start the Telemetry Ingestion Worker
Connects to Dev 1's live WebSocket feed and batches vitals into Tiger Data:
```bash
python -m backend.services.ingestion_worker
```

### 5. Generate Morning Recap via CLI
Test the Gemini morning summary directly from terminal:
```bash
python -m backend.services.gemini_summary
```

---

## 📡 API Endpoints Reference

| Method | Endpoint | Description | Consumed By |
| --- | --- | --- | --- |
| `GET` | `/api/health` | Verifies DB connection & record counts | System / Monitor |
| `GET` | `/api/nightly-summary` | Aggregates sleep metrics & calls Gemini for 3-bullet recap | **Dev 2 (Dashboard)** |
| `GET` | `/api/sleep-timeline` | Chronological sleep states (`ASLEEP`, `RESTLESS`, etc.) | **Dev 2 (Sleep Blocks)** |
| `GET` | `/api/vitals-trend` | Downsampled breathing (BrPM) & pulse (BPM) data points | **Dev 2 (Sparklines)** |
| `POST` | `/api/soothe-events` | Logs trigger & resolution of auto-soothe intervention | **Dev 3 (Audio Engine)** |

### Example Payload: `POST /api/soothe-events`
```json
{
  "triggered_at": "2026-10-09T14:30:00Z",
  "resolved_at": "2026-10-09T14:30:42Z",
  "voice_snippet_used": "Shh, you're safe, go back to sleep Maya.",
  "was_successful": true
}
```

### Example Response: `GET /api/nightly-summary?baby_name=Maya`
```json
{
  "baby_name": "Maya",
  "model_used": "gemini-3.5-flash-lite",
  "summary_bullets": [
    "🌙 Maya enjoyed a peaceful 8 hours in her crib, getting a full night of solid rest to help her wake up refreshed.",
    "🕊️ When 3 brief moments of restlessness popped up, CradleEcho's gentle auto-soothe stepped in and smoothly guided her back to dreamland in under 30 seconds every time.",
    "💜 Her breathing rate held steady and calm all night long between 20 and 30 breaths per minute, giving you complete peace of mind while you slept."
  ],
  "metrics": {
    "sleep_hours": 8.0,
    "estimated_total_hours": 8.0,
    "avg_brpm": 24.3,
    "avg_bpm": 109.1,
    "restless_spikes_count": 2,
    "soothe_interventions_count": 2,
    "avg_soothe_resolve_seconds": 40
  }
}
```

---

## 🔒 Safety Rails & Compliance
- **Not a medical device**: CradleEcho is an informational wellness monitor, not a medical or SIDS-prevention device.
- Derived biometrics only are stored; video feeds are processed locally on the edge daemon and not persisted.