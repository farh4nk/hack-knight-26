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
  SIMULATE_RESTLESS_URL,
  STALE_AFTER_MS,
  WS_URL,
} from "@/lib/config";
import { startMockTelemetry, type MockTelemetrySource } from "@/lib/mockTelemetry";
import { isTelemetry, type Telemetry } from "@/lib/types";

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
  /** Forces RESTLESS for 15s (daemon endpoint, or the mock generator). */
  simulateRestless: () => Promise<void>;
}

const TelemetryContext = createContext<TelemetryContextValue | null>(null);

const MIN_RETRY_MS = 1000;
const MAX_RETRY_MS = 5000;

export function TelemetryProvider({ children }: { children: ReactNode }) {
  const [latest, setLatest] = useState<Telemetry | null>(null);
  const [history, setHistory] = useState<Telemetry[]>([]);
  const [connected, setConnected] = useState(MOCK);
  const [stale, setStale] = useState(true);
  const lastMessageAt = useRef(0);
  const mockSource = useRef<MockTelemetrySource | null>(null);

  const handleMessage = useCallback((t: Telemetry) => {
    lastMessageAt.current = Date.now();
    setStale(false);
    setLatest(t);
    setHistory((prev) => [...prev.slice(-(HISTORY_LENGTH - 1)), t]);
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
      ws = new WebSocket(WS_URL);
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
      setStale(Date.now() - lastMessageAt.current > STALE_AFTER_MS);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const simulateRestless = useCallback(async () => {
    if (MOCK) {
      mockSource.current?.simulateRestless();
      return;
    }
    try {
      const res = await fetch(SIMULATE_RESTLESS_URL, { method: "POST" });
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

  return (
    <TelemetryContext.Provider
      value={{ latest, history, connected, stale, mock: MOCK, simulateRestless }}
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
