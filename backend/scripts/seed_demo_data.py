"""
Realistic overnight demo data seeder for Cribby (Dev 4).
Populates baby_vitals and soothe_events with an 8-hour sleep session
(e.g., 10:00 PM to 6:00 AM) including:
- Baseline calm sleep (22-26 BrPM, 105-115 BPM)
- 2 restlessness episodes
- 2 successful auto-soothe interventions (resolving in ~35-45 seconds)
"""

import datetime
import random
from backend.db.connection import get_db_connection, is_postgres
from backend.services.gemini_summary import get_night_window

def generate_night_data(bedtime: str = "20:00", wake_time: str = "07:00"):
    now = datetime.datetime.now(datetime.timezone.utc)
    start_time, end_time = get_night_window(bedtime, wake_time, as_of=now)
    
    # 2 restlessness events during the night:
    # Event 1: ~3.5 hours into sleep
    # Event 2: ~7.5 hours into sleep
    restless_1_start = start_time + datetime.timedelta(hours=3, minutes=24)
    restless_1_resolve = restless_1_start + datetime.timedelta(seconds=42)

    restless_2_start = start_time + datetime.timedelta(hours=7, minutes=18)
    restless_2_resolve = restless_2_start + datetime.timedelta(seconds=38)

    soothe_events = [
        {
            "triggered_at": restless_1_start.isoformat(),
            "resolved_at": restless_1_resolve.isoformat(),
            "voice_snippet_used": "Shhh.",
            "was_successful": True,
        },
        {
            "triggered_at": restless_2_start.isoformat(),
            "resolved_at": restless_2_resolve.isoformat(),
            "voice_snippet_used": "Go to sleep.",
            "was_successful": True,
        }
    ]

    vitals = []
    current_time = start_time
    # Downsampled step of 10s across the scheduled crib window
    step_seconds = 10

    while current_time <= end_time:
        # Check if in restlessness window
        is_restless_1 = restless_1_start <= current_time <= restless_1_resolve
        is_restless_2 = restless_2_start <= current_time <= restless_2_resolve

        if is_restless_1 or is_restless_2:
            state = "RESTLESS"
            brpm = round(random.uniform(32.0, 36.5), 1)
            bpm = round(random.uniform(122.0, 134.0), 1)
            motion = round(random.uniform(0.65, 0.88), 2)
            confidence = round(random.uniform(0.85, 0.94), 2)
        else:
            # Normal calm sleep with gentle pediatric rhythm
            state = "ASLEEP"
            brpm = round(random.uniform(22.0, 26.0) + (0.5 * random.random()), 1)
            bpm = round(random.uniform(104.0, 114.0), 1)
            motion = round(random.uniform(0.02, 0.12), 2)
            confidence = round(random.uniform(0.90, 0.98), 2)

        vitals.append((
            current_time.isoformat(),
            state,
            brpm,
            bpm,
            confidence,
            motion
        ))
        current_time += datetime.timedelta(seconds=step_seconds)

    return vitals, soothe_events

def seed(bedtime: str = "20:00", wake_time: str = "07:00"):
    print(f"Generating realistic sleep telemetry for bedtime {bedtime} to wake {wake_time}...")
    vitals, soothe_events = generate_night_data(bedtime=bedtime, wake_time=wake_time)
    print(f"Generated {len(vitals)} vitals data points and {len(soothe_events)} soothe events.")

    with get_db_connection() as conn:
        cur = conn.cursor()
        try:
            # Clear existing seed data if needed
            cur.execute("DELETE FROM baby_vitals;")
            cur.execute("DELETE FROM soothe_events;")

            # Insert vitals
            if is_postgres():
                cur.executemany(
                    """
                    INSERT INTO baby_vitals (time, state, breathing_rate, heart_rate, confidence, motion_index)
                    VALUES (%s, %s, %s, %s, %s, %s);
                    """,
                    vitals
                )
                for event in soothe_events:
                    cur.execute(
                        """
                        INSERT INTO soothe_events (triggered_at, resolved_at, voice_snippet_used, was_successful)
                        VALUES (%s, %s, %s, %s);
                        """,
                        (event["triggered_at"], event["resolved_at"], event["voice_snippet_used"], event["was_successful"])
                    )
            else:
                cur.executemany(
                    """
                    INSERT INTO baby_vitals (time, state, breathing_rate, heart_rate, confidence, motion_index)
                    VALUES (?, ?, ?, ?, ?, ?);
                    """,
                    vitals
                )
                for event in soothe_events:
                    cur.execute(
                        """
                        INSERT INTO soothe_events (triggered_at, resolved_at, voice_snippet_used, was_successful)
                        VALUES (?, ?, ?, ?);
                        """,
                        (event["triggered_at"], event["resolved_at"], event["voice_snippet_used"], event["was_successful"])
                    )
        finally:
            cur.close()

    print(f"Successfully seeded database with scheduled {bedtime} - {wake_time} sleep metrics!")

if __name__ == "__main__":
    seed()
