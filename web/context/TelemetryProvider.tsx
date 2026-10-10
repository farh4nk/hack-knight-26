"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  HISTORY_LENGTH,
  MOCK,
  STALE_AFTER_MS,
  cameraUrl,
  daemonUrl,
  simulateRestlessUrl,
  wsUrl,
} from "@/lib/config";
import { startMockTelemetry, type MockTelemetrySource } from "@/lib/mockTelemetry";
import { toneOf } from "@/lib/stateCopy";
import { isTelemetry, type Telemetry } from "@/lib/types";
import { useActivity, type ActivityEvent } from "@/lib/useActivity";

export interface TelemetryContextValue {
  /** Most recent packet, or null before the first one arrives. */
  latest: Telemetry | null;
  /** Rolling window of recent packets, oldest first (~60s). */
  history: Telemetry[];
  /** WebSocket is open (always true in mock mode). */
  connected: boolean;
  /** No packet received for STALE_AFTER_MS. */
  stale: boolean;
  mock: boolean;
  /** Active telemetry mode on the edge daemon: SIMULATED (mock) vs REALTIME (camera). */
  sourceMode: "SIMULATED" | "REALTIME";
  /** Switches daemon between simulated data and real optical camera sensor. */
  setSourceMode: (mode: "mock" | "real") => Promise<void>;
  /** State changes since the page opened, newest first. */
  events: ActivityEvent[];
  /** When the current state began (ms since epoch), as observed by this page. */
  stateSince: number | null;
  /** Desktop notifications for state changes (need https or localhost). */
  alerts: { supported: boolean; enabled: boolean; set: (on: boolean) => Promise<void> };
  /** Forces RESTLESS for 15s (daemon endpoint, or the mock generator). */
  simulateRestless: () => Promise<void>;
  /** Turn the camera on/off. Off stops capture and the Presage session (no credits used). */
  setCameraEnabled: (enabled: boolean) => Promise<void>;
}

const TelemetryContext = createContext<TelemetryContextValue | null>(null);

const MIN_RETRY_MS = 1000;
const MAX_RETRY_MS = 5000;

export function TelemetryProvider({ children }: { children: ReactNode }) {
  const [latest, setLatest] = useState<Telemetry | null>(null);
  const [history, setHistory] = useState<Telemetry[]>([]);
  const [connected, setConnected] = useState(MOCK);
  const [stale, setStale] = useState(true);
  const [sourceMode, setSourceModeState] = useState<"SIMULATED" | "REALTIME">("SIMULATED");
  const { events, stateSince, record, alerts } = useActivity();
  const lastMessageAt = useRef(0);
  const mockSource = useRef<MockTelemetrySource | null>(null);

  const handleMessage = useCallback((t: Telemetry) => {
    lastMessageAt.current = Date.now();
    setStale(false);
    setLatest(t);
    if (t.mode) {
      setSourceModeState(t.mode);
    }
    setHistory((prev) => [...prev.slice(-(HISTORY_LENGTH - 1)), t]);
    record(toneOf(t, false), t.camera);
  }, [record]);

  // Query initial mode from daemon
  useEffect(() => {
    let cancelled = false;
    fetch(`${daemonUrl()}/api/source`)
      .then((res) => res.json())
      .then((data) => {
        if (!cancelled && data.mode) {
          setSourceModeState(data.mode);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const setSourceMode = useCallback(async (mode: "mock" | "real") => {
    try {
      const res = await fetch(`${daemonUrl()}/api/source`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source: mode }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.mode) setSourceModeState(data.mode);
      }
    } catch (e) {
      console.warn("Failed to toggle source mode on daemon:", e);
    }
  }, []);

  // Data source: in-browser mock, or the daemon WebSocket with reconnect backoff.
  useEffect(() => {
    if (MOCK) {
      mockSource.current = startMockTelemetry(handleMessage);
      return () => {
        mockSource.current?.stop();
        mockSource.current = null;
      };
    }

    let ws: WebSocket | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let retryMs = MIN_RETRY_MS;
    let disposed = false;

    const connect = () => {
      ws = new WebSocket(wsUrl());
      ws.onopen = () => {
        retryMs = MIN_RETRY_MS;
        setConnected(true);
      };
      ws.onmessage = (event) => {
        try {
          const data: unknown = JSON.parse(event.data);
          if (isTelemetry(data)) handleMessage(data);
        } catch {
          // Ignore malformed packets.
        }
      };
      ws.onclose = () => {
        setConnected(false);
        if (disposed) return;
        retryTimer = setTimeout(connect, retryMs);
        retryMs = Math.min(retryMs * 2, MAX_RETRY_MS);
      };
      ws.onerror = () => ws?.close();
    };

    connect();
    return () => {
      disposed = true;
      clearTimeout(retryTimer);
      ws?.close();
    };
  }, [handleMessage]);

  // Staleness watchdog.
  useEffect(() => {
    const timer = setInterval(() => {
      const isStale = Date.now() - lastMessageAt.current > STALE_AFTER_MS;
      setStale(isStale);
      if (isStale && lastMessageAt.current > 0) record("offline");
    }, 1000);
    return () => clearInterval(timer);
  }, [record]);

  const simulateRestless = useCallback(async () => {
    if (MOCK) {
      mockSource.current?.simulateRestless();
      return;
    }
    try {
      const res = await fetch(simulateRestlessUrl(), { method: "POST" });
      if (res.ok) return;
    } catch {
      console.warn("Daemon offline; simulating restlessness directly in-browser.");
    }

    // Graceful fallback: simulate restless episode locally if daemon endpoint fails
    const nowIso = new Date().toISOString();
    handleMessage({
      timestamp: nowIso,
      state: "RESTLESS",
      vitals: { brpm: 34.5, bpm: 122.0, confidence: 0.92 },
      motion_index: 0.76,
    });
    setTimeout(() => {
      handleMessage({
        timestamp: new Date().toISOString(),
        state: "ASLEEP",
        vitals: { brpm: 24.0, bpm: 108.0, confidence: 0.95 },
        motion_index: 0.06,
      });
    }, 15000);
  }, [handleMessage]);

  const setCameraEnabled = useCallback(async (enabled: boolean) => {
    if (MOCK) {
      mockSource.current?.setCameraEnabled(enabled);
      return;
    }
    const res = await fetch(cameraUrl(), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    });
    if (!res.ok) throw new Error(`Couldn’t turn the camera ${enabled ? "on" : "off"} (HTTP ${res.status})`);
  }, []);

  return (
    <TelemetryContext.Provider
      value={{
        latest,
        history,
        connected,
        stale,
        mock: MOCK,
        sourceMode,
        setSourceMode,
        events,
        stateSince,
        alerts,
        simulateRestless,
        setCameraEnabled,
      }}
    >
      {children}
    </TelemetryContext.Provider>
  );
}

export function useTelemetry(): TelemetryContextValue {
  const ctx = useContext(TelemetryContext);
  if (!ctx) throw new Error("useTelemetry must be used inside <TelemetryProvider>");
  return ctx;
}
