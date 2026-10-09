"use client";

import { useSyncExternalStore } from "react";
import { daemonUrl } from "./config";

const noopSubscribe = () => () => {};

/** Daemon base URL for rendering; null on the server and during hydration (no mismatch). */
export function useDaemonUrl(): string | null {
  return useSyncExternalStore(noopSubscribe, daemonUrl, () => null);
}
