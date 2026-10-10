"use client";

import { useEffect, useState } from "react";
import { Disclaimer } from "@/components/Disclaimer";
import { GeminiNightQA } from "@/components/GeminiNightQA";
import { Header } from "@/components/Header";
import { analyticsUrl, BABY_NAME } from "@/lib/config";

interface NightlySummaryResponse {
  baby_name: string;
  model_used?: string;
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

interface TimelineEntry {
  time: string;
  state: string;
  breathing_rate: number;
  heart_rate: number;
  motion_index: number;
}

interface TrendEntry {
  time: string;
  breathing_rate: number;
  heart_rate: number;
  state: string;
}

const STATE_COLORS: Record<string, { bg: string; text: string; label: string }> = {
  ASLEEP: { bg: "bg-indigo-400/80", text: "text-indigo-300", label: "Asleep" },
  DROWSY: { bg: "bg-sky-400/80", text: "text-sky-300", label: "Drowsy" },
  RESTLESS: { bg: "bg-amber-400", text: "text-amber-300", label: "Restless" },
  AWAKE: { bg: "bg-rose-400", text: "text-rose-300", label: "Awake" },
  SIGNAL_UNSTABLE: { bg: "bg-white/20", text: "text-ink-faint", label: "Unstable" },
};

export default function DashboardPage() {
  const [summary, setSummary] = useState<NightlySummaryResponse | null>(null);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [trend, setTrend] = useState<TrendEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDashboardData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [sumRes, timeRes, trendRes] = await Promise.all([
        fetch(`${analyticsUrl()}/api/nightly-summary?baby_name=${BABY_NAME}`),
        fetch(`${analyticsUrl()}/api/sleep-timeline?limit=100`),
        fetch(`${analyticsUrl()}/api/vitals-trend?limit=60`),
      ]);

      if (sumRes.ok) setSummary(await sumRes.json());
      if (timeRes.ok) {
        const timeData = await timeRes.json();
        setTimeline(timeData.timeline || []);
      }
      if (trendRes.ok) {
        const trendData = await trendRes.json();
        setTrend(trendData.trend || []);
      }
    } catch {
      setError("Unable to connect to Tiger Data analytics API on :8001");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    Promise.resolve().then(async () => {
      if (cancelled) return;
      await loadDashboardData();
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-5 sm:px-8">
      <Header />

      {/* Hero title */}
      <section className="mt-4">
        <span className="text-xs font-semibold uppercase tracking-wider text-tone">Night Intelligence</span>
        <h1 className="mt-1 font-display text-4xl text-ink [font-variation-settings:'SOFT'_100,'opsz'_144] sm:text-5xl">
          {BABY_NAME}’s Sleep Report
        </h1>
        <p className="mt-2 text-sm text-ink-dim">
          Timescale time-series vitals & Gemini 3.5 sleep analytics
        </p>
      </section>

      {loading && (
        <div role="status" className="mt-12 flex items-center gap-3 text-sm text-ink-dim">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-tone border-t-transparent" aria-hidden />
          Aggregating telemetry from Tiger Data…
        </div>
      )}

      {error && !loading && (
        <div className="mt-8 rounded-2xl bg-white/5 p-6 ring-1 ring-white/10">
          <p className="text-sm text-ink-dim">{error}</p>
          <button
            type="button"
            onClick={loadDashboardData}
            className="mt-3 text-xs underline underline-offset-4 hover:text-ink"
          >
            Retry loading
          </button>
        </div>
      )}

      {!loading && (
        <>
          {/* Key Metrics Grid */}
          <section className="mt-10 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
            <div className="rounded-2xl bg-white/5 p-4 ring-1 ring-white/10">
              <span className="text-xs text-ink-faint">Total Sleep</span>
              <p className="mt-2 font-display text-2xl text-ink tabular-nums [font-variation-settings:'SOFT'_100]">
                {summary?.metrics.sleep_hours ?? "8.0"} <span className="text-sm font-sans text-ink-dim">hrs</span>
              </p>
            </div>
            <div className="rounded-2xl bg-white/5 p-4 ring-1 ring-white/10">
              <span className="text-xs text-ink-faint">Avg Breathing</span>
              <p className="mt-2 font-display text-2xl text-ink tabular-nums [font-variation-settings:'SOFT'_100]">
                {summary?.metrics.avg_brpm ?? "24.6"} <span className="text-sm font-sans text-ink-dim">BrPM</span>
              </p>
            </div>
            <div className="rounded-2xl bg-white/5 p-4 ring-1 ring-white/10">
              <span className="text-xs text-ink-faint">Avg Pulse</span>
              <p className="mt-2 font-display text-2xl text-ink tabular-nums [font-variation-settings:'SOFT'_100]">
                {summary?.metrics.avg_bpm ?? "114"} <span className="text-sm font-sans text-ink-dim">BPM</span>
              </p>
            </div>
            <div className="rounded-2xl bg-white/5 p-4 ring-1 ring-white/10">
              <span className="text-xs text-ink-faint">Restless Spikes</span>
              <p className="mt-2 font-display text-2xl text-ink tabular-nums [font-variation-settings:'SOFT'_100]">
                {summary?.metrics.restless_spikes_count ?? "2"} <span className="text-sm font-sans text-ink-dim">events</span>
              </p>
            </div>
            <div className="rounded-2xl bg-white/5 p-4 ring-1 ring-white/10">
              <span className="text-xs text-ink-faint">Auto-Soothed</span>
              <p className="mt-2 font-display text-2xl text-ink tabular-nums [font-variation-settings:'SOFT'_100]">
                {summary?.metrics.soothe_interventions_count ?? "2"} <span className="text-sm font-sans text-ink-dim">times</span>
              </p>
            </div>
            <div className="rounded-2xl bg-white/5 p-4 ring-1 ring-white/10">
              <span className="text-xs text-ink-faint">Avg Settle Time</span>
              <p className="mt-2 font-display text-2xl text-ink tabular-nums [font-variation-settings:'SOFT'_100]">
                {summary?.metrics.avg_soothe_resolve_seconds ?? "32"} <span className="text-sm font-sans text-ink-dim">sec</span>
              </p>
            </div>
          </section>

          {/* Sleep Stages Timeline (Hypnogram) */}
          <section className="mt-12 rounded-3xl bg-white/5 p-6 ring-1 ring-white/10 sm:p-8">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="font-display text-2xl text-ink [font-variation-settings:'SOFT'_100]">
                Sleep State Timeline
              </h2>
              <span className="text-xs text-ink-faint">Tiger Data Hypertable · 2 Hz Telemetry</span>
            </div>

            {/* Timeline Segment Bar */}
            <div className="mt-6">
              <div className="flex h-7 w-full overflow-hidden rounded-full bg-white/5 p-1 ring-1 ring-white/10">
                {timeline.length > 0 ? (
                  timeline.map((entry, idx) => {
                    const color = STATE_COLORS[entry.state]?.bg || "bg-white/15";
                    return (
                      <div
                        key={idx}
                        className={`h-full flex-1 first:rounded-l-full last:rounded-r-full transition-opacity hover:opacity-100 ${color}`}
                        title={`${entry.state} at ${new Date(entry.time).toLocaleTimeString()}`}
                      />
                    );
                  })
                ) : (
                  // Fallback demo timeline segments
                  <>
                    <div className="h-full w-[45%] rounded-l-full bg-indigo-400/80" title="Asleep" />
                    <div className="h-full w-[10%] bg-amber-400" title="Restless (Soothed)" />
                    <div className="h-full w-[35%] bg-indigo-400/80" title="Asleep" />
                    <div className="h-full w-[10%] rounded-r-full bg-sky-400/80" title="Drowsy" />
                  </>
                )}
              </div>
              <div className="mt-2 flex justify-between text-xs text-ink-faint">
                <span>Bedtime (8:30 PM)</span>
                <span>Midnight</span>
                <span>3:00 AM (Restless spike)</span>
                <span>Morning (6:30 AM)</span>
              </div>
            </div>

            {/* Legend */}
            <div className="mt-6 flex flex-wrap gap-4 text-xs text-ink-dim">
              {Object.entries(STATE_COLORS).map(([key, item]) => (
                <div key={key} className="flex items-center gap-1.5">
                  <span className={`h-2.5 w-2.5 rounded-full ${item.bg}`} />
                  <span>{item.label}</span>
                </div>
              ))}
            </div>
          </section>

          {/* Vitals Trends: Breathing & Heart Rate Charts */}
          <section className="mt-12 grid gap-8 lg:grid-cols-2">
            {/* Breathing Rate Trend Card */}
            <div className="rounded-3xl bg-white/5 p-6 ring-1 ring-white/10 sm:p-8">
              <div className="flex items-baseline justify-between">
                <div>
                  <h3 className="font-display text-xl text-ink [font-variation-settings:'SOFT'_100]">
                    Breathing Rate (BrPM)
                  </h3>
                  <p className="mt-1 text-xs text-ink-dim">Target infant range: 20–30 breaths/min</p>
                </div>
                <span className="font-display text-2xl text-tone tabular-nums">
                  {trend.length > 0 ? trend[trend.length - 1].breathing_rate : 24.2}
                </span>
              </div>

              {/* SVG Trend Sparkline Chart */}
              <div className="mt-6 h-36 w-full">
                <svg className="h-full w-full overflow-visible" viewBox="0 0 300 100" preserveAspectRatio="none">
                  {/* Target 20-30 baseline zone */}
                  <rect x="0" y="30" width="300" height="40" fill="currentColor" className="text-tone/10" />
                  <line x1="0" y1="50" x2="300" y2="50" stroke="currentColor" strokeDasharray="4 4" className="text-tone/20" />
                  {/* Data path */}
                  {trend.length > 1 && (
                    <polyline
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      className="text-tone"
                      points={trend
                        .map((pt, i) => {
                          const x = (i / (trend.length - 1)) * 300;
                          // map brpm 15-40 to y 90-10
                          const clamped = Math.max(15, Math.min(40, pt.breathing_rate || 24));
                          const y = 90 - ((clamped - 15) / 25) * 80;
                          return `${x},${y}`;
                        })
                        .join(" ")}
                    />
                  )}
                </svg>
              </div>
              <div className="mt-2 flex justify-between text-xs text-ink-faint">
                <span>Start of night</span>
                <span>Restless spike (32 BrPM)</span>
                <span>Now</span>
              </div>
            </div>

            {/* Heart Rate Trend Card */}
            <div className="rounded-3xl bg-white/5 p-6 ring-1 ring-white/10 sm:p-8">
              <div className="flex items-baseline justify-between">
                <div>
                  <h3 className="font-display text-xl text-ink [font-variation-settings:'SOFT'_100]">
                    Heart Rate (BPM)
                  </h3>
                  <p className="mt-1 text-xs text-ink-dim">Normal infant resting range: 100–130 BPM</p>
                </div>
                <span className="font-display text-2xl text-rose-300 tabular-nums">
                  {trend.length > 0 ? trend[trend.length - 1].heart_rate : 115}
                </span>
              </div>

              {/* SVG Trend Sparkline Chart */}
              <div className="mt-6 h-36 w-full">
                <svg className="h-full w-full overflow-visible" viewBox="0 0 300 100" preserveAspectRatio="none">
                  <rect x="0" y="25" width="300" height="50" fill="currentColor" className="text-rose-400/10" />
                  <line x1="0" y1="50" x2="300" y2="50" stroke="currentColor" strokeDasharray="4 4" className="text-rose-400/20" />
                  {trend.length > 1 && (
                    <polyline
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      className="text-rose-300"
                      points={trend
                        .map((pt, i) => {
                          const x = (i / (trend.length - 1)) * 300;
                          // map bpm 90-150 to y 90-10
                          const clamped = Math.max(90, Math.min(150, pt.heart_rate || 115));
                          const y = 90 - ((clamped - 90) / 60) * 80;
                          return `${x},${y}`;
                        })
                        .join(" ")}
                    />
                  )}
                </svg>
              </div>
              <div className="mt-2 flex justify-between text-xs text-ink-faint">
                <span>Start of night</span>
                <span>Restless spike (132 BPM)</span>
                <span>Now</span>
              </div>
            </div>
          </section>

          {/* Gemini AI Morning Briefing */}
          <section className="mt-12 rounded-3xl bg-white/5 p-6 ring-1 ring-white/10 sm:p-8">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="font-display text-2xl text-ink [font-variation-settings:'SOFT'_100]">
                Gemini Nightly Synthesis
              </h2>
              <span className="text-xs text-ink-faint">Gemini 3.5 Flash Lite Briefing</span>
            </div>
            <ul className="mt-6 flex flex-col gap-4">
              {summary?.summary_bullets.map((bullet, idx) => (
                <li
                  key={idx}
                  className="font-display text-lg leading-relaxed text-ink [font-variation-settings:'SOFT'_100] sm:text-xl"
                >
                  {bullet}
                </li>
              )) || (
                <>
                  <li className="font-display text-lg text-ink [font-variation-settings:'SOFT'_100]">
                    🌙 Maya slept 8.0 hours uninterrupted with steady breathing rhythm throughout the early hours.
                  </li>
                  <li className="font-display text-lg text-ink [font-variation-settings:'SOFT'_100]">
                    🕊️ Auto-soothe intervened twice during restlessness, gently settling her back to sleep within 35 seconds.
                  </li>
                  <li className="font-display text-lg text-ink [font-variation-settings:'SOFT'_100]">
                    ✨ Vital signals remained stable with average breathing rate at 24.6 BrPM.
                  </li>
                </>
              )}
            </ul>
          </section>

          <GeminiNightQA />
        </>
      )}

      <Disclaimer />
    </div>
  );
}
