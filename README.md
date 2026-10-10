# Cribby

> Real-time infant wellness monitor with non-contact vitals, ElevenLabs cloned-voice auto-soothing, Tiger Data storage, and Gemini morning summaries.

---

## ⚡ Quickstart

### 1. Environment Setup
```bash
cp .env.example .env
cp web/.env.example web/.env.local
```
Fill in `.env` with:
- `DATABASE_URL`: Tiger Data / Timescale connection string
- `GEMINI_API_KEY`: Google AI Studio key
- `ELEVENLABS_API_KEY`: ElevenLabs key (also in `web/.env.local`)

### 2. Database (Tiger Data)
```bash
# Run schema migrations
python -m backend.db.migrate

# Seed 8 hours of realistic sleep demo data
python -m backend.scripts.seed_demo_data
```

### 3. Run Services

| Service | Directory | Command | URL |
|---|---|---|---|
| **Web Frontend** | `web/` | `npm run dev` | `http://localhost:3000` |
| **Analytics API** | Root | `uvicorn backend.api.app:app --port 8001 --reload` | `http://localhost:8001` |
| **CV Daemon** | `daemon/` | `python -m cradleecho` | `http://localhost:8000` |
| **Ingestion Worker** | Root | `python -m backend.services.ingestion_worker` | Background |

---

## 🔌 Core API Endpoints

- `GET /api/nightly-summary`: Gemini 3-bullet morning report from Tiger Data metrics.
- `GET /api/sleep-timeline`: Chronological sleep state segments.
- `GET /api/vitals-trend`: Downsampled BrPM & BPM sparkline data.
- `POST /api/soothe-events`: Log auto-soothe intervention trigger/resolution.
- `POST /api/elevenlabs/clone`: Instant voice clone from 10s audio sample.
- `POST /api/elevenlabs/tts`: Text-to-speech in cloned parent voice.

---

## 🛡️ Safety
Cribby is an informational wellness monitor, not a medical or SIDS-prevention device. Biometrics are derived locally; video is never persisted.