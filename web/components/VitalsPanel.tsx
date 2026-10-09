"use client";

import { useTelemetry } from "@/context/TelemetryProvider";
import { MIN_CONFIDENCE } from "@/lib/config";
import type { Telemetry } from "@/lib/types";
import { Sparkline } from "./Sparkline";

const trusted = (t: Telemetry) => t.state !== "SIGNAL_UNSTABLE" && t.vitals.confidence >= MIN_CONFIDENCE;

interface VitalProps {
  label: string;
  unit: string;
  pick: (t: Telemetry) => number;
  decimals: number;
  minSpan: number;
}

function Vital({ label, unit, pick, decimals, minSpan }: VitalProps) {
  const { latest, history, stale } = useTelemetry();
  const ok = latest !== null && !stale && trusted(latest);
  const series = history.filter(trusted).slice(-60).map(pick);

  return (
    <div>
      <div className="flex items-baseline justify-between">
        <span className="text-sm text-ink-dim">{label}</span>
        <span className="text-xs text-ink-faint">last minute</span>
      </div>
      <div className="mt-1 flex items-baseline gap-2">
        <span
          className={`font-display text-6xl tabular-nums tracking-tight [font-variation-settings:'SOFT'_100,'opsz'_144] ${
            ok ? "text-ink" : "text-ink-faint"
          }`}
        >
          {ok && latest ? pick(latest).toFixed(decimals) : "—"}
        </span>
        <span className="text-sm text-ink-dim">{unit}</span>
      </div>
      <Sparkline values={series} minSpan={minSpan} className={`mt-3 text-tone transition-opacity duration-700 ${ok ? "" : "opacity-30"}`} />
      {!ok && <p className="mt-1 text-sm text-ink-faint">Waiting for a clear reading.</p>}
    </div>
  );
}

export function VitalsPanel() {
  return (
    <section className="flex flex-col gap-9">
      <Vital label="Breathing" unit="breaths / min" pick={(t) => t.vitals.brpm} decimals={0} minSpan={8} />
      <div className="h-px bg-line" />
      <Vital label="Heart" unit="beats / min" pick={(t) => t.vitals.bpm} decimals={0} minSpan={20} />
    </section>
  );
}
