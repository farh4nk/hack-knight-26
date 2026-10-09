"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { SootheEngine, SootheEngineOptions, SootheSnapshot } from "@/lib/audio/soothe-engine";
import { SoothingSnippet } from "@/lib/audio/elevenlabs";

const noopSubscribe = () => () => {};

/**
 * Wires the soothe engine to the telemetry stream.
 * Pass the current `state` from useTelemetry().
 */
export function useAutoSoothe(
  state?: string | null,
  snippets: SoothingSnippet[] = [],
  options: SootheEngineOptions = {}
) {
  const onEventRef = useRef(options.onEvent);
  onEventRef.current = options.onEvent;

  const [engine] = useState(
    () => new SootheEngine({ ...options, onEvent: (e) => onEventRef.current?.(e) })
  );

  const snapshot: SootheSnapshot = useSyncExternalStore(
    engine.subscribe ?? noopSubscribe,
    engine.getSnapshot,
    engine.getSnapshot
  );

  useEffect(() => () => engine.destroy(), [engine]);
  useEffect(() => engine.setSnippets(snippets), [engine, snippets]);
  useEffect(() => {
    if (state) engine.onTelemetry({ state });
  }, [engine, state]);

  return { engine, snapshot };
}
