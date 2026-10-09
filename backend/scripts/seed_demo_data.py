"""
Realistic overnight demo data seeder for CradleEcho (Dev 4).
Populates baby_vitals and soothe_events with an 8-hour sleep session
(e.g., 10:00 PM to 6:00 AM) including:
- Baseline calm sleep (22-26 BrPM, 105-115 BPM)
- 2 restlessness episodes
- 2 successful auto-soothe interventions (resolving in ~35-45 seconds)
"""

import datetime
import random
from backend.db.connection import get_db_connection, is_postgres

def generate_night_data():
    now = datetime.datetime.now(datetime.timezone.utc)
    # Start 8 hours ago
    start_time = now - datetime.timedelta(hours=8)
    
    # 2 restlessness events during the night:
    # Event 1: 2.5 hours after falling asleep
    # Event 2: 5.5 hours after falling asleep
    restless_1_start = start_time + datetime.timedelta(hours=2, minutes=30)
    restless_1_resolve = restless_1_start + datetime.timedelta(seconds=42)

    restless_2_start = start_time + datetime.timedelta(hours=5, minutes=35)
    restless_2_resolve = restless_2_start + datetime.timedelta(seconds=38)

    soothe_events = [
        {
            "triggered_at": restless_1_start.isoformat(),
            "resolved_at": restless_1_resolve.isoformat(),
            "voice_snippet_used": "Shh, you're safe, go back to sleep Maya.",
            "was_successful": True,
        },
        {
            "triggered_at": restless_2_start.isoformat(),
            "resolved_at": restless_2_resolve.isoformat(),
            "voice_snippet_used": "Mommy and daddy are right here, sweet dreams.",
            "was_successful": True,
        }
    ]

    vitals = []
    current_time = start_time
    # Telemetry emitted at 2 Hz (every 0.5s), downsampled to every 5s for the demo seed (5,760 points over 8 hours)
    step_seconds = 5

    while current_time <= now:
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
            # Normal sleep with natural gentle fluctuations
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

def seed():
    print("Generating 8 hours of realistic sleep telemetry...")
    vitals, soothe_events = generate_night_data()
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

    print("Successfully seeded database with 8 hours of sleep metrics!")

if __name__ == "__main__":
    seed()
