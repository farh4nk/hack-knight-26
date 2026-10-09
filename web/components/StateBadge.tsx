"use client";

import { useTelemetry } from "@/context/TelemetryProvider";
import type { SleepState } from "@/lib/types";

const BADGES: Record<SleepState, { label: string; className: string }> = {
  ASLEEP: {
    label: "Asleep",
    className: "bg-emerald-500/90 text-emerald-950",
  },
  DROWSY: {
    label: "Drowsy",
    className: "bg-indigo-400/90 text-indigo-950",
  },
  RESTLESS: {
    label: "Restless — Auto-Soothe Primed",
    className: "bg-amber-400/95 text-amber-950 animate-pulse",
  },
  AWAKE: {
    label: "Awake",
    className: "bg-rose-500/95 text-white",
  },
  SIGNAL_UNSTABLE: {
    label: "Signal Unstable — Adjust Crib Lighting",
    className: "bg-slate-500/90 text-white",
  },
};

export function StateBadge() {
  const { latest, connected, stale } = useTelemetry();

  const badge =
    !connected || stale || !latest
      ? { label: "Disconnected — Waiting for Monitor", className: "bg-slate-800/90 text-slate-300" }
      : BADGES[latest.state];

  return (
    <div
      role="status"
      aria-live="polite"
      className={`inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-sm font-semibold shadow-lg backdrop-blur ${badge.className}`}
    >
      <span className="h-2 w-2 rounded-full bg-current opacity-70" />
      {badge.label}
    </div>
  );
}
