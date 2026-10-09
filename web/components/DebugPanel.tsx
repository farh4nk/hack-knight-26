"use client";

import { useTelemetry } from "@/context/TelemetryProvider";

export function DebugPanel() {
  const { latest } = useTelemetry();
  return (
    <details className="rounded-2xl bg-slate-900 p-4 text-sm text-slate-400 ring-1 ring-white/10">
      <summary className="cursor-pointer select-none">Raw telemetry</summary>
      <pre className="mt-3 overflow-x-auto text-xs text-slate-300">
        {latest ? JSON.stringify(latest, null, 2) : "No packets yet"}
      </pre>
    </details>
  );
}
