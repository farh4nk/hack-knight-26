// Temporary product name; change it here only.
export const APP_NAME = "CradleEcho";

const DAEMON_PORT = 8000;

/**
 * Base URL of the daemon (video, telemetry, API). Browser-only values: call this from effects and
 * event handlers, or use `useDaemonUrl()` when rendering.
 *
 * Unset NEXT_PUBLIC_DAEMON_URL means "the host that served this page, on port 8000". That is what
 * makes the UI work from any device when the Pi serves both the UI and the daemon (a hard-coded
 * localhost would point a laptop at itself).
 */
export function daemonUrl(): string {
  const fromEnv = process.env.NEXT_PUBLIC_DAEMON_URL;
  if (fromEnv) return fromEnv.replace(/\/$/, "");
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:${DAEMON_PORT}`;
  }
  return `http://localhost:${DAEMON_PORT}`;
}

/** Analytics API (nightly summary, soothe-event log). Same host-relative rule as the daemon, port 8001. */
export function analyticsUrl(): string {
  const fromEnv = process.env.NEXT_PUBLIC_ANALYTICS_URL;
  if (fromEnv) return fromEnv.replace(/\/$/, "");
  if (typeof window !== "undefined") return `${window.location.protocol}//${window.location.hostname}:8001`;
  return "http://localhost:8001";
}

export const wsUrl = () => `${daemonUrl().replace(/^http/, "ws")}/ws/telemetry`;
export const videoFeedUrl = (debug = false) =>
  // The debug feed has the daemon's face-gate and vitals overlay drawn on it.
  `${daemonUrl()}${debug ? "/video_feed/debug" : "/video_feed"}`;
export const simulateRestlessUrl = () => `${daemonUrl()}/api/simulate-restless`;
export const cameraUrl = () => `${daemonUrl()}/api/camera`;
export const edgeSoothePlayUrl = () => `${daemonUrl()}/api/soothe/play`;
export const edgeSootheStopUrl = () => `${daemonUrl()}/api/soothe/stop`;

export const talkWsUrl = () => `${daemonUrl().replace(/^http/, "ws")}/ws/talk`;
export const listenWsUrl = () => `${daemonUrl().replace(/^http/, "ws")}/ws/listen`;
export const nightVisionUrl = () => `${daemonUrl()}/api/night-vision`;
export const audioCapabilitiesUrl = () => `${daemonUrl()}/api/audio/capabilities`;

// Generate telemetry in the browser instead of connecting to the daemon.
export const MOCK = process.env.NEXT_PUBLIC_MOCK === "1";

// Below this, vitals are not trusted (matches the daemon's SIGNAL_UNSTABLE gate).
export const MIN_CONFIDENCE = 0.4;

export const TELEMETRY_HZ = 2;
export const HISTORY_LENGTH = 120; // ~60s at 2 Hz
export const STALE_AFTER_MS = 3000;
export const SIMULATE_RESTLESS_MS = 15000;
