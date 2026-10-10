"use client";

import { useEffect, useState } from "react";
import { babyTitle, getBabyName } from "@/lib/babyName";
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
      const res = await fetch(`${analyticsUrl()}/api/nightly-summary?baby_name=${encodeURIComponent(babyTitle(getBabyName()))}`);
      if (!res.ok) throw new Error("Could not load summary");
      const json = await res.json();
      setData(json);
    } catch {
setError("Tiger Data / Gemini service currently offline");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    Promise.resolve().then(async () => {
      if (cancelled) return;
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`${analyticsUrl()}/api/nightly-summary?baby_name=${encodeURIComponent(babyTitle(getBabyName()))}`);
        if (!res.ok) throw new Error("Could not load summary");
        const json = await res.json();
        if (!cancelled) setData(json);
      } catch {
        if (!cancelled) setError("Tiger Data / Gemini service currently offline");
      } finally {
        if (!cancelled) setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="mt-16 border-t border-line pt-10">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-display text-3xl text-ink [font-variation-settings:'SOFT'_100,'opsz'_144]">Last night</h2>
        <span className="text-xs text-ink-faint">Summary by Gemini · data on Tiger Data</span>
      </div>

      {loading && (
        <div role="status" className="mt-6 flex items-center gap-2.5 text-sm text-ink-dim">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-tone border-t-transparent" aria-hidden />
          Reading through the night…
        </div>
      )}

      {error && !loading && (
        <p className="mt-6 text-sm text-ink-faint">
          {error}{" "}
          <button type="button" onClick={fetchSummary} className="underline underline-offset-4 hover:text-ink">
            Try again
          </button>
        </p>
      )}

      {data && !loading && (
        <div className="mt-6 grid gap-10 lg:grid-cols-[minmax(0,1fr)_16rem]">
          <ul className="flex flex-col gap-4">
            {data.summary_bullets.map((bullet, idx) => (
              <li key={idx} className="font-display text-xl leading-snug text-ink [font-variation-settings:'SOFT'_100]">
                {bullet}
              </li>
            ))}
          </ul>
          <dl className="grid grid-cols-3 gap-4 text-sm lg:grid-cols-1">
            <div>
              <dt className="text-ink-faint">Slept</dt>
              <dd className="font-display text-2xl text-ink tabular-nums">{data.metrics.sleep_hours} h</dd>
            </div>
            <div>
              <dt className="text-ink-faint">Avg breathing</dt>
              <dd className="font-display text-2xl text-ink tabular-nums">{data.metrics.avg_brpm}</dd>
            </div>
            <div>
              <dt className="text-ink-faint">Soothed</dt>
              <dd className="font-display text-2xl text-ink tabular-nums">{data.metrics.soothe_interventions_count}×</dd>
            </div>
          </dl>
        </div>
      )}
    </section>
  );
}
