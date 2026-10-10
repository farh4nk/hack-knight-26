"""
FastAPI Analytics & Summary Server (Dev 4).
Exposes:
- GET /api/nightly-summary: AI morning recap from Gemini & Tiger Data (Task 4.3)
- GET /api/sleep-timeline: Chronological state transitions for Dev 2 timeline
- GET /api/vitals-trend: Downsampled time-series vitals for Dev 2 sparklines
- POST /api/soothe-events: Logs auto-soothe intervention events from Dev 3
- GET /api/health: Service and database status check
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import datetime
from backend.db.connection import get_db_connection, is_postgres, test_connection
from backend.services.gemini_summary import fetch_nightly_metrics, generate_morning_brief

app = FastAPI(
    title="CradleEcho Analytics & Summary API",
    description="Time-series telemetry storage with Tiger Data and Gemini morning recaps",
    version="1.0.0"
)

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SootheEventCreate(BaseModel):
    triggered_at: Optional[str] = None
    resolved_at: Optional[str] = None
    voice_snippet_used: str
    was_successful: bool = True

@app.get("/api/health")
def health_check():
    """Health check endpoint showing database connectivity and sample stats."""
    db_ok = test_connection()
    if not db_ok:
        raise HTTPException(status_code=503, detail="Database connection unavailable")
    
    with get_db_connection() as conn:
        cur = conn.cursor()
        try:
            cur.execute("SELECT count(*) as vitals_count FROM baby_vitals;")
            vitals_count = cur.fetchone()["vitals_count"]
            cur.execute("SELECT count(*) as soothe_count FROM soothe_events;")
            soothe_count = cur.fetchone()["soothe_count"]
        finally:
            cur.close()

    return {
        "status": "healthy",
        "database": "Tiger Data PostgreSQL" if is_postgres() else "Local SQLite Fallback",
        "vitals_records": vitals_count,
        "soothe_records": soothe_count,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }

@app.get("/api/nightly-summary")
def get_nightly_summary(baby_name: str = "Maya", hours: int = 12):
    """Task 4.3: Aggregates night vitals from Tiger Data and prompts Gemini for a 3-bullet recap."""
    try:
        metrics = fetch_nightly_metrics(hours=hours)
        summary = generate_morning_brief(metrics, baby_name=baby_name)
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sleep-timeline")
def get_sleep_timeline(limit: int = 100):
    """Returns chronological timeline segments for Dev 2's sleep status block chart."""
    with get_db_connection() as conn:
        cur = conn.cursor()
        try:
            # Query recent entries ordered chronologically
            cur.execute(
                """
                SELECT time, state, breathing_rate, heart_rate, motion_index
                FROM baby_vitals
                ORDER BY time ASC
                LIMIT %s;
                """ if is_postgres() else """
                SELECT time, state, breathing_rate, heart_rate, motion_index
                FROM baby_vitals
                ORDER BY time ASC
                LIMIT ?;
                """,
                (limit,)
            )
            rows = cur.fetchall()
            return {"timeline": [dict(r) for r in rows]}
        finally:
            cur.close()

@app.get("/api/vitals-trend")
def get_vitals_trend(limit: int = 60):
    """Returns downsampled vitals for Dev 2 sparkline charts (breathing and pulse rates)."""
    with get_db_connection() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT time, breathing_rate, heart_rate, state
                FROM baby_vitals
                ORDER BY time DESC
                LIMIT %s;
                """ if is_postgres() else """
                SELECT time, breathing_rate, heart_rate, state
                FROM baby_vitals
                ORDER BY time DESC
                LIMIT ?;
                """,
                (limit,)
            )
            rows = cur.fetchall()
            # Return reversed so frontend receives it in ascending chronological order
            trend_data = [dict(r) for r in reversed(rows)]
            return {"trend": trend_data}
        finally:
            cur.close()

@app.post("/api/soothe-events")
def record_soothe_event(event: SootheEventCreate):
    """Task 3/4 integration: records auto-soothe intervention events from Dev 3's audio engine."""
    triggered_at = event.triggered_at or datetime.datetime.now(datetime.timezone.utc).isoformat()
    resolved_at = event.resolved_at or datetime.datetime.now(datetime.timezone.utc).isoformat()

    with get_db_connection() as conn:
        cur = conn.cursor()
        try:
            if is_postgres():
                cur.execute(
                    """
                    INSERT INTO soothe_events (triggered_at, resolved_at, voice_snippet_used, was_successful)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id;
                    """,
                    (triggered_at, resolved_at, event.voice_snippet_used, event.was_successful)
                )
                event_id = cur.fetchone()["id"]
            else:
                cur.execute(
                    """
                    INSERT INTO soothe_events (triggered_at, resolved_at, voice_snippet_used, was_successful)
                    VALUES (?, ?, ?, ?);
                    """,
                    (triggered_at, resolved_at, event.voice_snippet_used, event.was_successful)
                )
                event_id = cur.lastrowid
        finally:
            cur.close()

    return {
        "status": "recorded",
        "id": event_id,
        "triggered_at": triggered_at,
        "resolved_at": resolved_at,
        "voice_snippet_used": event.voice_snippet_used,
        "was_successful": event.was_successful
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.api.app:app", host="0.0.0.0", port=8001, reload=True)
