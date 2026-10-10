"use client";

import { useTelemetry } from "@/context/TelemetryProvider";
import { TONE_HEX, toneOf, type Tone } from "@/lib/stateCopy";

/** The last minute as a colored band: how the state has moved. */
export function StateRibbon() {
  const { history } = useTelemetry();

  const runs: { tone: Tone; count: number }[] = [];
  for (const t of history) {
    const tone = toneOf(t, false);
    const last = runs[runs.length - 1];
    if (last && last.tone === tone) last.count++;
    else runs.push({ tone, count: 1 });
  }

  return (
    <section aria-label="State over the last minute">
      <div className="flex h-2.5 gap-px overflow-hidden rounded-full bg-white/5">
        {runs.map((r, i) => (
          <div
            key={i}
            style={{ flexGrow: r.count, backgroundColor: TONE_HEX[r.tone], opacity: 0.85 }}
            className="min-w-[2px] first:rounded-l-full last:rounded-r-full"
          />
        ))}
      </div>
      <div className="mt-2 flex justify-between text-xs text-ink-faint">
        <span>1 min ago</span>
        <span>now</span>
      </div>
    </section>
  );
}
