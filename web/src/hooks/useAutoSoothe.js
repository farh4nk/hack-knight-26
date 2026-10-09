import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { SootheEngine } from "../lib/audio/soothe-engine.js";

const noopSubscribe = () => () => {};

/**
 * Wires the soothe engine to the telemetry stream.
 * Pass the current `state` from the telemetry context.
 */
export function useAutoSoothe(state, snippets, options = {}) {
  const onEventRef = useRef(options.onEvent);
  onEventRef.current = options.onEvent;

  // Created once. StrictMode's dev double-effect is safe: destroy() only stops audio/listeners.
  const [engine] = useState(() => new SootheEngine({ ...options, onEvent: (e) => onEventRef.current?.(e) }));

  const snapshot = useSyncExternalStore(engine.subscribe ?? noopSubscribe, engine.getSnapshot);

  useEffect(() => () => engine.destroy(), [engine]);
  useEffect(() => engine.setSnippets(snippets), [engine, snippets]);
  useEffect(() => {
    if (state) engine.onTelemetry({ state });
  }, [engine, state]);

  return { engine, snapshot };
}
