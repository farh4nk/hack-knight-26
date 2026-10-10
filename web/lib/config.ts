// Temporary product name; change it here only.
export const APP_NAME = "Cribby";

const DAEMON_PORT = 8000;
const ANALYTICS_PORT = 8001;

/**
 * Base URL of the daemon (video, telemetry, API). Browser-only values: call this from effects and
 * event handlers, or use `useDaemonUrl()` when rendering.
 *
 * Unset NEXT_PUBLIC_DAEMON_URL means "the host that served this page, on port 8000". That is what
 * makes the UI work from any device when the Pi serves both the UI and the daemon (a hard-coded
 * localhost would point a laptop at itself).
 *
 * When served over HTTPS via Caddy (same origin), the daemon is reachable at /daemon and analytics
 * at /analytics — no port needed. Plain-HTTP behavior stays exactly as is (host:8000 / host:8001).
 */
export function daemonUrl(): string {
  const fromEnv = process.env.NEXT_PUBLIC_DAEMON_URL;
  if (fromEnv) return fromEnv.replace(/\/$/, "");
  if (typeof window !== "undefined") {
    const isHttps = window.location.protocol === "https:";
    if (isHttps) {
      // Same-origin through Caddy: /daemon proxies to daemon:8000
      return `${window.location.origin}/daemon`;
    }
    return `${window.location.protocol}//${window.location.hostname}:${DAEMON_PORT}`;
  }
  return `http://localhost:${DAEMON_PORT}`;
}

/** Analytics API (nightly summary, soothe-event log). Same host-relative rule as the daemon. */
export function analyticsUrl(): string {
  const fromEnv = process.env.NEXT_PUBLIC_ANALYTICS_URL;
  if (fromEnv) return fromEnv.replace(/\/$/, "");
  if (typeof window !== "undefined") {
    const isHttps = window.location.protocol === "https:";
    if (isHttps) {
      // Same-origin through Caddy: /analytics proxies to analytics:8001
      return `${window.location.origin}/analytics`;
    }
    return `${window.location.protocol}//${window.location.hostname}:${ANALYTICS_PORT}`;
  }
  return `http://localhost:${ANALYTICS_PORT}`;
}

/**
 * Base URL of the edge unit (the Pi that owns the speaker, mic and camera device) when it is a
 * different machine from the daemon that runs Presage (see docs/presage-compute.md). Unset means
 * a single box: the edge is the daemon.
 */
export function edgeUrl(): string {
  const fromEnv = process.env.NEXT_PUBLIC_EDGE_URL;
  return fromEnv ? fromEnv.replace(/\/$/, "") : daemonUrl();
}

/** True when the edge unit is a different machine from the daemon. */
export const hasSeparateEdge = () => edgeUrl() !== daemonUrl();

export const wsUrl = () => `${daemonUrl().replace(/^http/, "ws")}/ws/telemetry`;
export const videoFeedUrl = (debug = false) =>
  // The debug feed has the daemon's face-gate and vitals overlay drawn on it.
  `${daemonUrl()}${debug ? "/video_feed/debug" : "/video_feed"}`;
export const simulateRestlessUrl = () => `${daemonUrl()}/api/simulate-restless`;
export const cameraUrl = () => `${daemonUrl()}/api/camera`;
// Hardware-owned actions go to the edge unit; vitals, state and soothe decisions stay on the daemon.
export const edgeSoothePlayUrl = () => `${edgeUrl()}/api/soothe/play`;
export const edgeSootheStopUrl = () => `${edgeUrl()}/api/soothe/stop`;

export const talkWsUrl = () => `${edgeUrl().replace(/^http/, "ws")}/ws/talk`;
export const listenWsUrl = () => `${edgeUrl().replace(/^http/, "ws")}/ws/listen`;
export const nightVisionUrl = () => `${edgeUrl()}/api/night-vision`;
export const audioCapabilitiesUrl = () => `${edgeUrl()}/api/audio/capabilities`;

// Generate telemetry in the browser instead of connecting to the daemon.
export const MOCK = process.env.NEXT_PUBLIC_MOCK === "1";

// Below this, vitals are not trusted (matches the daemon's SIGNAL_UNSTABLE gate).
export const MIN_CONFIDENCE = 0.4;

export const TELEMETRY_HZ = 2;
export const HISTORY_LENGTH = 120; // ~60s at 2 Hz
export const STALE_AFTER_MS = 3000;
export const SIMULATE_RESTLESS_MS = 15000;
