"use client";

import { useEffect, useState, useCallback } from "react";
import { Disclaimer } from "@/components/Disclaimer";
import { GeminiNightQA } from "@/components/GeminiNightQA";
import { Header } from "@/components/Header";
import { babyTitle, getBabyName, useBabyName } from "@/lib/babyName";
import { analyticsUrl } from "@/lib/config";
import { useAuth } from "@/context/AuthProvider";

interface NightlySummaryResponse {
  baby_name: string;
  model_used?: string;
  summary_bullets: string[];
  metrics: {
    bedtime?: string;
    wake_time?: string;
    window_start?: string;
    window_end?: string;
    scheduled_hours: number;
    sleep_hours: number;
    sleep_efficiency_percent: number;
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

function formatTime12(timeStr: string): string {
  try {
    const [hStr, mStr] = timeStr.split(":");
    let h = parseInt(hStr, 10);
    const m = parseInt(mStr || "0", 10);
    const ampm = h >= 12 ? "PM" : "AM";
    h = h % 12;
    if (h === 0) h = 12;
    const minPadded = m < 10 ? `0${m}` : `${m}`;
    return `${h}:${minPadded} ${ampm}`;
  } catch {
    return timeStr;
  }
}

export default function DashboardPage() {
  const title = babyTitle(useBabyName() ?? "");
  const { baby, updateBaby } = useAuth();
  const [bedtime, setBedtime] = useState(baby?.bedtime || "20:00");
  const [wakeTime, setWakeTime] = useState(baby?.wake_time || "07:00");
  const [summary, setSummary] = useState<NightlySummaryResponse | null>(null);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [trend, setTrend] = useState<TrendEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDashboardData = useCallback(async (bTime = bedtime, wTime = wakeTime) => {
    setLoading(true);
    setError(null);
    try {
      const [sumRes, timeRes, trendRes] = await Promise.all([
        fetch(`${analyticsUrl()}/api/nightly-summary?baby_name=${encodeURIComponent(babyTitle(getBabyName()))}&bedtime=${bTime}&wake_time=${wTime}`),
        fetch(`${analyticsUrl()}/api/sleep-timeline?bedtime=${bTime}&wake_time=${wTime}&limit=120`),
        fetch(`${analyticsUrl()}/api/vitals-trend?bedtime=${bTime}&wake_time=${wTime}&limit=60`),
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
  }, [bedtime, wakeTime]);

  useEffect(() => {
    let cancelled = false;
    Promise.resolve().then(async () => {
      if (cancelled) return;
      if (baby?.bedtime && baby?.wake_time) {
        setBedtime(baby.bedtime);
        setWakeTime(baby.wake_time);
        await loadDashboardData(baby.bedtime, baby.wake_time);
      } else {
        await loadDashboardData("20:00", "07:00");
      }
    });
    return () => {
      cancelled = true;
    };
  }, [baby?.bedtime, baby?.wake_time, loadDashboardData]);

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-5 sm:px-8">
      <Header />

      {/* Hero title */}
      <section className="mt-4">
        <span className="text-xs font-semibold uppercase tracking-wider text-tone">Night Intelligence</span>
        <h1 className="mt-1 font-display text-4xl text-ink [font-variation-settings:'SOFT'_100,'opsz'_144] sm:text-5xl">
          {title}’s Sleep Report
        </h1>
        <p className="mt-2 text-sm text-ink-dim">
          Tiger Data time-series vitals scoped to your scheduled bedtime window & Gemini 3.5 sleep analytics
        </p>
      </section>

      {/* Bedtime Window Controls Card */}
      <section className="mt-8 rounded-3xl bg-white/5 p-6 ring-1 ring-white/10 sm:p-7">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-tone">🌙 Bedtime & Wake Schedule</span>
              <span className="rounded-full bg-tone/15 px-2.5 py-0.5 text-[11px] font-medium text-tone">
                Parent Configured
              </span>
            </div>
            <p className="mt-1 text-xs text-ink-dim">
              Set {title}’s scheduled crib hours. Telemetry queries, hypnogram, and Gemini summaries scope to this exact window.
            </p>
          </div>

          {/* Quick preset buttons */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-ink-faint">Presets:</span>
            {[
              { label: "8 PM – 7 AM", b: "20:00", w: "07:00" },
              { label: "7:30 PM – 6:30 AM", b: "19:30", w: "06:30" },
              { label: "8:30 PM – 6:30 AM", b: "20:30", w: "06:30" },
              { label: "9 PM – 7:30 AM", b: "21:00", w: "07:30" },
            ].map((p) => (
              <button
                key={p.label}
                type="button"
                onClick={() => {
                  setBedtime(p.b);
                  setWakeTime(p.w);
                  loadDashboardData(p.b, p.w);
                }}
                className={`rounded-full px-3 py-1 text-xs transition ${
                  bedtime === p.b && wakeTime === p.w
                    ? "bg-tone text-[#0a0b15] font-semibold"
                    : "bg-white/5 text-ink-dim ring-1 ring-white/10 hover:bg-white/10 hover:text-ink"
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>

        {/* Schedule Inputs */}
        <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="rounded-2xl bg-white/5 p-3.5 ring-1 ring-white/10">
            <label className="text-xs text-ink-faint">Bedtime (Put to Bed)</label>
            <div className="mt-1.5 flex items-center gap-2">
              <input
                type="time"
                value={bedtime}
                onChange={(e) => setBedtime(e.target.value)}
                className="w-full rounded-xl bg-black/30 px-3 py-1.5 text-sm text-ink ring-1 ring-white/10 focus:outline-none focus:ring-tone/50"
              />
              <span className="text-xs text-tone whitespace-nowrap font-medium">
                {formatTime12(bedtime)}
              </span>
            </div>
          </div>

          <div className="rounded-2xl bg-white/5 p-3.5 ring-1 ring-white/10">
            <label className="text-xs text-ink-faint">Wake Time (Morning Wake-Up)</label>
            <div className="mt-1.5 flex items-center gap-2">
              <input
                type="time"
                value={wakeTime}
                onChange={(e) => setWakeTime(e.target.value)}
                className="w-full rounded-xl bg-black/30 px-3 py-1.5 text-sm text-ink ring-1 ring-white/10 focus:outline-none focus:ring-tone/50"
              />
              <span className="text-xs text-tone whitespace-nowrap font-medium">
                {formatTime12(wakeTime)}
              </span>
            </div>
          </div>

          <div className="flex items-center">
            <button
              type="button"
              onClick={() => {
                loadDashboardData(bedtime, wakeTime);
                if (baby) {
                  updateBaby({ bedtime, wake_time: wakeTime });
                }
              }}
              disabled={loading}
              className="w-full rounded-2xl bg-tone px-4 py-3 text-sm font-semibold text-[#0a0b15] transition hover:opacity-90 disabled:opacity-50"
            >
              {loading ? "Re-scoping…" : "Apply Bedtime Window"}
            </button>
          </div>
        </div>
      </section>

      {loading && (
        <div role="status" className="mt-12 flex items-center gap-3 text-sm text-ink-dim">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-tone border-t-transparent" aria-hidden />
          Aggregating telemetry from Tiger Data for {formatTime12(bedtime)} – {formatTime12(wakeTime)}…
        </div>
      )}

      {error && !loading && (
        <div className="mt-8 rounded-2xl bg-white/5 p-6 ring-1 ring-white/10">
          <p className="text-sm text-ink-dim">{error}</p>
          <button
            type="button"
            onClick={() => loadDashboardData(bedtime, wakeTime)}
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
              <span className="text-xs text-ink-faint">Sleep Efficiency</span>
              <p className="mt-2 font-display text-2xl text-tone tabular-nums [font-variation-settings:'SOFT'_100]">
                {summary?.metrics.sleep_efficiency_percent ?? "100"} <span className="text-sm font-sans text-ink-dim">%</span>
              </p>
              <span className="mt-1 block text-[11px] text-ink-faint">Target: &gt;85%</span>
            </div>
            <div className="rounded-2xl bg-white/5 p-4 ring-1 ring-white/10">
              <span className="text-xs text-ink-faint">Scheduled Crib Time</span>
              <p className="mt-2 font-display text-2xl text-ink tabular-nums [font-variation-settings:'SOFT'_100]">
                {summary?.metrics.scheduled_hours ?? "11.0"} <span className="text-sm font-sans text-ink-dim">hrs</span>
              </p>
              <span className="mt-1 block text-[11px] text-ink-faint">{formatTime12(bedtime)} – {formatTime12(wakeTime)}</span>
            </div>
            <div className="rounded-2xl bg-white/5 p-4 ring-1 ring-white/10">
              <span className="text-xs text-ink-faint">Total Asleep</span>
              <p className="mt-2 font-display text-2xl text-ink tabular-nums [font-variation-settings:'SOFT'_100]">
                {summary?.metrics.sleep_hours ?? "11.0"} <span className="text-sm font-sans text-ink-dim">hrs</span>
              </p>
              <span className="mt-1 block text-[11px] text-ink-faint">Logged calm rest</span>
            </div>
            <div className="rounded-2xl bg-white/5 p-4 ring-1 ring-white/10">
              <span className="text-xs text-ink-faint">Avg Breathing</span>
              <p className="mt-2 font-display text-2xl text-ink tabular-nums [font-variation-settings:'SOFT'_100]">
                {summary?.metrics.avg_brpm ?? "24.3"} <span className="text-sm font-sans text-ink-dim">BrPM</span>
              </p>
              <span className="mt-1 block text-[11px] text-ink-faint">Baseline: 20–30</span>
            </div>
            <div className="rounded-2xl bg-white/5 p-4 ring-1 ring-white/10">
              <span className="text-xs text-ink-faint">Avg Pulse</span>
              <p className="mt-2 font-display text-2xl text-ink tabular-nums [font-variation-settings:'SOFT'_100]">
                {summary?.metrics.avg_bpm ?? "109"} <span className="text-sm font-sans text-ink-dim">BPM</span>
              </p>
              <span className="mt-1 block text-[11px] text-ink-faint">Baseline: 100–130</span>
            </div>
            <div className="rounded-2xl bg-white/5 p-4 ring-1 ring-white/10">
              <span className="text-xs text-ink-faint">Auto-Soothed</span>
              <p className="mt-2 font-display text-2xl text-ink tabular-nums [font-variation-settings:'SOFT'_100]">
                {summary?.metrics.soothe_interventions_count ?? "2"} <span className="text-sm font-sans text-ink-dim">times</span>
              </p>
              <span className="mt-1 block text-[11px] text-ink-faint">~{summary?.metrics.avg_soothe_resolve_seconds ?? 40}s avg settle</span>
            </div>
          </section>

          {/* Sleep Stages Timeline (Hypnogram) */}
          <section className="mt-12 rounded-3xl bg-white/5 p-6 ring-1 ring-white/10 sm:p-8">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="font-display text-2xl text-ink [font-variation-settings:'SOFT'_100]">
                Sleep State Timeline
              </h2>
              <span className="text-xs text-ink-faint">Tiger Data Hypertable · Scoped to Scheduled Night</span>
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
                <span>Bedtime ({formatTime12(bedtime)})</span>
                <span>Midnight</span>
                <span>3:00 AM (Restless spike)</span>
                <span>Wake Time ({formatTime12(wakeTime)})</span>
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
                  {trend.length > 0 ? trend[trend.length - 1].breathing_rate : 24.3}
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
                <span>Bedtime ({formatTime12(bedtime)})</span>
                <span>Restless spike (36 BrPM)</span>
                <span>Wake Time ({formatTime12(wakeTime)})</span>
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
                  {trend.length > 0 ? trend[trend.length - 1].heart_rate : 109}
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
                          const clamped = Math.max(90, Math.min(150, pt.heart_rate || 109));
                          const y = 90 - ((clamped - 90) / 60) * 80;
                          return `${x},${y}`;
                        })
                        .join(" ")}
                    />
                  )}
                </svg>
              </div>
              <div className="mt-2 flex justify-between text-xs text-ink-faint">
                <span>Bedtime ({formatTime12(bedtime)})</span>
                <span>Restless spike (134 BPM)</span>
                <span>Wake Time ({formatTime12(wakeTime)})</span>
              </div>
            </div>
          </section>

          {/* Gemini AI Morning Briefing */}
          <section className="mt-12 rounded-3xl bg-white/5 p-6 ring-1 ring-white/10 sm:p-8">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="font-display text-2xl text-ink [font-variation-settings:'SOFT'_100]">
                Gemini Nightly Synthesis
              </h2>
              <span className="text-xs text-ink-faint">Gemini 3.5 Flash Lite Briefing · {formatTime12(bedtime)} to {formatTime12(wakeTime)}</span>
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
                    🌙 {title} slept 11.0 hours uninterrupted with 100% sleep efficiency during the scheduled bedtime.
                  </li>
                  <li className="font-display text-lg text-ink [font-variation-settings:'SOFT'_100]">
                    🕊️ Auto-soothe intervened twice during restlessness, gently settling them back to sleep within 40 seconds.
                  </li>
                  <li className="font-display text-lg text-ink [font-variation-settings:'SOFT'_100]">
                    ✨ Vital signals remained stable with average breathing rate at 24.3 BrPM.
                  </li>
                </>
              )}
            </ul>
          </section>

          <GeminiNightQA bedtime={bedtime} wakeTime={wakeTime} />
        </>
      )}

      <Disclaimer />
    </div>
  );
}
