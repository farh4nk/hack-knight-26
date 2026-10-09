"""
Telemetry Ingestion Worker (Task 4.2).
Connects to Dev 1's WebSocket stream (ws://localhost:8000/ws/telemetry),
buffers incoming 2 Hz telemetry JSON packets in-memory,
and performs a batch insert into Tiger Data (baby_vitals) every 5 seconds.
Includes exponential backoff auto-reconnect.
"""

import os
import json
import asyncio
import logging
import datetime
from typing import List, Tuple
import websockets
from dotenv import load_dotenv
from backend.db.connection import get_db_connection, is_postgres

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cradleecho.ingest")

WS_URL = os.getenv("TELEMETRY_WS_URL", "ws://localhost:8000/ws/telemetry")
FLUSH_INTERVAL = float(os.getenv("INGESTION_INTERVAL_SECONDS", "5"))

class TelemetryIngestionWorker:
    def __init__(self, ws_url: str = WS_URL, flush_interval: float = FLUSH_INTERVAL):
        self.ws_url = ws_url
        self.flush_interval = flush_interval
        self.buffer: List[Tuple[str, str, float, float, float, float]] = []
        self.running = False
        self._lock = asyncio.Lock()

    def parse_payload(self, raw_data: str) -> Tuple[str, str, float, float, float, float] | None:
        """Parses and validates telemetry JSON packet against AGENTS.md contract."""
        try:
            payload = json.loads(raw_data)
            # Contract: timestamp, state, vitals: {brpm, bpm, confidence}, motion_index
            ts = payload.get("timestamp") or datetime.datetime.now(datetime.timezone.utc).isoformat()
            state = payload.get("state", "SIGNAL_UNSTABLE")
            vitals = payload.get("vitals", {})
            brpm = float(vitals.get("brpm", 0.0))
            bpm = float(vitals.get("bpm", 0.0))
            confidence = float(vitals.get("confidence", 0.0))
            motion = float(payload.get("motion_index", 0.0))

            return (ts, state, brpm, bpm, confidence, motion)
        except Exception as e:
            logger.warning(f"Failed to parse telemetry packet: {e} (Payload: {raw_data[:100]})")
            return None

    async def flush_batch(self):
        """Flushes the buffered telemetry batch to Tiger Data."""
        async with self._lock:
            if not self.buffer:
                return
            batch = self.buffer.copy()
            self.buffer.clear()

        try:
            with get_db_connection() as conn:
                cur = conn.cursor()
                try:
                    if is_postgres():
                        cur.executemany(
                            """
                            INSERT INTO baby_vitals (time, state, breathing_rate, heart_rate, confidence, motion_index)
                            VALUES (%s, %s, %s, %s, %s, %s);
                            """,
                            batch
                        )
                    else:
                        cur.executemany(
                            """
                            INSERT INTO baby_vitals (time, state, breathing_rate, heart_rate, confidence, motion_index)
                            VALUES (?, ?, ?, ?, ?, ?);
                            """,
                            batch
                        )
                finally:
                    cur.close()
            logger.info(f"Batched {len(batch)} telemetry rows inserted into Tiger Data.")
        except Exception as e:
            logger.error(f"Error flushing batch to Tiger Data: {e}")
            # Put items back in buffer to avoid losing telemetry data on transient error
            async with self._lock:
                self.buffer = batch + self.buffer

    async def flush_loop(self):
        """Periodic worker task that flushes the buffer every flush_interval seconds."""
        while self.running:
            await asyncio.sleep(self.flush_interval)
            await self.flush_batch()

    async def run(self):
        """Main connection loop with auto-reconnect exponential backoff."""
        self.running = True
        flush_task = asyncio.create_task(self.flush_loop())
        backoff = 1

        logger.info(f"Starting Telemetry Ingestion Worker (target WS: {self.ws_url})...")
        while self.running:
            try:
                logger.info(f"Connecting to telemetry WebSocket: {self.ws_url}...")
                async with websockets.connect(self.ws_url) as ws:
                    logger.info("Connected to telemetry stream! Receiving live vitals...")
                    backoff = 1
                    async for message in ws:
                        item = self.parse_payload(message)
                        if item:
                            async with self._lock:
                                self.buffer.append(item)
            except (websockets.exceptions.ConnectionClosed, OSError) as e:
                logger.warning(f"WebSocket disconnected ({e}). Retrying in {backoff}s...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)
            except Exception as e:
                logger.error(f"Unexpected error in ingestion worker: {e}. Retrying in {backoff}s...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)

        flush_task.cancel()
        await self.flush_batch()

if __name__ == "__main__":
    worker = TelemetryIngestionWorker()
    try:
        asyncio.run(worker.run())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user.")
