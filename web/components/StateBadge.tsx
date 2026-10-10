"use client";

import { useTelemetry } from "@/context/TelemetryProvider";
import { copyFor, toneFor } from "@/lib/stateCopy";

/** Glass pill on the video: the live state at a glance. */
export function StateBadge() {
  const { latest, connected, stale } = useTelemetry();
  const tone = toneFor(latest?.state, !connected || stale || !latest);
  const { pill } = copyFor(tone, latest?.camera);

  return (
    <div
      role="status"
      className="inline-flex items-center gap-2 rounded-full bg-black/40 px-3.5 py-1.5 text-sm font-medium text-ink ring-1 ring-white/15 backdrop-blur-md"
    >
      <span className={`h-2 w-2 rounded-full bg-tone ${tone === "restless" ? "breathe" : ""}`} aria-hidden />
      {pill}
    </div>
  );
}
