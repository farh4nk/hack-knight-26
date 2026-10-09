// Temporary product name; change it here only.
export const APP_NAME = "CradleEcho";

export const DAEMON_URL = (
  process.env.NEXT_PUBLIC_DAEMON_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

export const WS_URL = `${DAEMON_URL.replace(/^http/, "ws")}/ws/telemetry`;
export const VIDEO_FEED_URL = `${DAEMON_URL}/video_feed`;
export const SIMULATE_RESTLESS_URL = `${DAEMON_URL}/api/simulate-restless`;

// Generate telemetry in the browser instead of connecting to the daemon.
export const MOCK = process.env.NEXT_PUBLIC_MOCK === "1";

// Below this, vitals are not trusted (matches the daemon's SIGNAL_UNSTABLE gate).
export const MIN_CONFIDENCE = 0.4;

export const TELEMETRY_HZ = 2;
export const HISTORY_LENGTH = 120; // ~60s at 2 Hz
export const STALE_AFTER_MS = 3000;
export const SIMULATE_RESTLESS_MS = 15000;
