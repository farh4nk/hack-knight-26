"use client";

import { useEffect, useState } from "react";
import { analyticsUrl } from "@/lib/config";


interface NightlySummaryResponse {
  baby_name: string;
  summary_bullets: string[];
  metrics: {
    sleep_hours: number;
    avg_brpm: number;
    avg_bpm: number;
    restless_spikes_count: number;
    soothe_interventions_count: number;
    avg_soothe_resolve_seconds: number;
  };
}

export function MorningRecapCard() {
  const [data, setData] = useState<NightlySummaryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchSummary = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${analyticsUrl()}/api/nightly-summary?baby_name=Maya`);
      if (!res.ok) throw new Error("Could not load summary");
      const json = await res.json();
      setData(json);
    } catch {
      setError("Tiger Data / Gemini service currently offline (run backend on :8001)");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSummary();
  }, []);

  return (
    <div className="rounded-2xl bg-slate-900 p-5 ring-1 ring-white/10">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-slate-400">Nightly Recap</span>
        <span className="rounded bg-violet-950 px-2 py-0.5 text-xs text-violet-400">Gemini 1.5 + Tiger Data</span>
      </div>

      {loading && (
        <div className="mt-4 flex items-center justify-center gap-2 py-3 text-xs text-slate-400">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-violet-400 border-t-transparent" />
          Analyzing night vitals…
        </div>
      )}

      {error && !loading && (
        <div className="mt-3 text-xs text-slate-500">
          <p>{error}</p>
          <button
            type="button"
            onClick={fetchSummary}
            className="mt-2 text-violet-400 underline hover:text-violet-300"
          >
            Retry
          </button>
        </div>
      )}

      {data && !loading && (
        <div className="mt-3 space-y-2">
          {data.summary_bullets.map((bullet, idx) => (
            <div key={idx} className="rounded-xl bg-slate-800/60 p-2.5 text-xs text-slate-300 leading-relaxed">
              {bullet}
            </div>
          ))}
          <div className="mt-2 flex justify-between border-t border-white/5 pt-2 text-[10px] text-slate-500">
            <span>Sleep: {data.metrics.sleep_hours}h</span>
            <span>Avg BrPM: {data.metrics.avg_brpm}</span>
            <span>Interventions: {data.metrics.soothe_interventions_count}</span>
          </div>
        </div>
      )}
    </div>
  );
}
