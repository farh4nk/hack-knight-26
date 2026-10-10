"use client";

import { useTelemetry } from "@/context/TelemetryProvider";
import { useBabyName } from "@/lib/babyName";
import { copyFor, toneOf } from "@/lib/stateCopy";
import { useNow } from "@/lib/useNow";

const clock = (ms: number) => new Date(ms).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });

function sinceLabel(since: number, now: number): string {
  const mins = Math.floor(Math.max(0, now - since) / 60000);
  if (mins < 1) return `Since ${clock(since)}`;
  if (mins < 60) return `Since ${clock(since)} · ${mins} min`;
  return `Since ${clock(since)} · ${Math.floor(mins / 60)} h ${mins % 60} min`;
}

/** One human sentence about how the baby is doing right now. */
export function StateHero() {
  const { latest, connected, stale, stateSince } = useTelemetry();
  const now = useNow();
  const tone = toneOf(latest, !connected || stale);
  const name = useBabyName() ?? "";
  const copy = copyFor(tone, latest?.camera, name);
  const showDuration = tone !== "offline" && stateSince !== null && now > 0;

  return (
    <section aria-live="polite" className="max-w-3xl">
      <div key={tone} className="rise">
        <h1 className="font-display text-[2.6rem] leading-[1.04] tracking-tight text-ink [font-variation-settings:'SOFT'_100,'opsz'_144] sm:text-6xl">
          {copy.headline}
        </h1>
        <p className="mt-4 text-lg text-ink-dim">{copy.detail}</p>
        {showDuration && <p className="mt-1 text-sm text-ink-faint">{sinceLabel(stateSince, now)}</p>}
      </div>
    </section>
  );
}
