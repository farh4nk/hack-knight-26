"use client";

import { useEffect, useState } from "react";
import { useTelemetry } from "@/context/TelemetryProvider";
import { SIMULATE_RESTLESS_MS } from "@/lib/config";

export function DemoControls() {
  const { simulateRestless, mock } = useTelemetry();
  const [lockedUntil, setLockedUntil] = useState(0);
  const [now, setNow] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const remaining = Math.max(0, Math.ceil((lockedUntil - now) / 1000));

  useEffect(() => {
    if (lockedUntil === 0) return;
    const timer = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(timer);
  }, [lockedUntil]);

  const trigger = async () => {
    setError(null);
    try {
      await simulateRestless();
      const t = Date.now();
      setNow(t);
      setLockedUntil(t + SIMULATE_RESTLESS_MS);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    }
  };

  return (
    <div className="rounded-2xl bg-slate-900 p-5 ring-1 ring-white/10">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-slate-400">Demo Controls</span>
        {mock && (
          <span className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-400">mock data</span>
        )}
      </div>
      <button
        type="button"
        onClick={trigger}
        disabled={remaining > 0}
        className="mt-3 w-full rounded-xl bg-amber-400 px-4 py-3 font-semibold text-amber-950 transition hover:bg-amber-300 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
      >
        {remaining > 0 ? `Restless simulated · ${remaining}s` : "Trigger Test Restlessness"}
      </button>
      {error && <p className="mt-2 text-sm text-rose-400">{error}</p>}
    </div>
  );
}
