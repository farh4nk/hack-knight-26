"use client";

import { useTelemetry } from "@/context/TelemetryProvider";
import { MIN_CONFIDENCE } from "@/lib/config";
import type { Telemetry } from "@/lib/types";
import { Sparkline } from "./Sparkline";

interface VitalsCardProps {
  label: string;
  unit: string;
  pick: (t: Telemetry) => number;
  decimals?: number;
  accentClassName: string;
}

const isTrusted = (t: Telemetry) =>
  t.state !== "SIGNAL_UNSTABLE" && t.vitals.confidence >= MIN_CONFIDENCE;

export function VitalsCard({ label, unit, pick, decimals = 0, accentClassName }: VitalsCardProps) {
  const { latest, history, stale } = useTelemetry();

  const trusted = latest !== null && !stale && isTrusted(latest);
  const value = trusted ? pick(latest).toFixed(decimals) : "—";
  const series = history.filter(isTrusted).map(pick);

  return (
    <div className="rounded-2xl bg-slate-900 p-5 ring-1 ring-white/10">
      <div className="text-sm font-medium text-slate-400">{label}</div>
      <div className="mt-1 flex items-baseline gap-2">
        <span className={`text-4xl font-semibold tabular-nums ${trusted ? "text-white" : "text-slate-600"}`}>
          {value}
        </span>
        <span className="text-sm text-slate-500">{unit}</span>
      </div>
      <Sparkline values={series} className={`mt-3 ${accentClassName}`} />
    </div>
  );
}

export function BreathingCard() {
  return (
    <VitalsCard
      label="Breathing Rate"
      unit="breaths/min"
      pick={(t) => t.vitals.brpm}
      decimals={1}
      accentClassName="text-sky-400"
    />
  );
}

export function HeartRateCard() {
  return (
    <VitalsCard
      label="Heart Rate"
      unit="bpm"
      pick={(t) => t.vitals.bpm}
      accentClassName="text-rose-400"
    />
  );
}
