"use client";

import { useTelemetry } from "@/context/TelemetryProvider";

// Secondary readouts: motion and Presage tracking confidence.
export function SignalStats() {
  const { latest, stale } = useTelemetry();
  const show = latest !== null && !stale;

  const stats = [
    { label: "Motion", value: show ? latest.motion_index.toFixed(2) : "—" },
    { label: "Signal confidence", value: show ? `${Math.round(latest.vitals.confidence * 100)}%` : "—" },
  ];

  return (
    <div className="grid grid-cols-2 gap-4">
      {stats.map((s) => (
        <div key={s.label} className="rounded-2xl bg-slate-900 p-4 ring-1 ring-white/10">
          <div className="text-xs font-medium text-slate-400">{s.label}</div>
          <div className="mt-1 text-2xl font-semibold tabular-nums text-white">{s.value}</div>
        </div>
      ))}
    </div>
  );
}
