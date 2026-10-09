"use client";

import { useCallback, useSyncExternalStore } from "react";

/** Current time in ms, refreshed every `intervalMs`. 0 on the server and during hydration. */
export function useNow(intervalMs = 10_000): number {
  const subscribe = useCallback(
    (cb: () => void) => {
      const id = setInterval(cb, intervalMs);
      return () => clearInterval(id);
    },
    [intervalMs],
  );
  return useSyncExternalStore(
    subscribe,
    () => Math.floor(Date.now() / intervalMs) * intervalMs,
    () => 0,
  );
}
