"use client";

import { useTelemetry } from "@/context/TelemetryProvider";
import { TONE_HEX } from "@/lib/stateCopy";

const time = (ms: number) => new Date(ms).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });

/** State changes since this page opened, plus the desktop-alerts switch. */
export function ActivityLog() {
  const { events, alerts } = useTelemetry();

  return (
    <section>
      <div className="flex items-center justify-between">
        <h2 className="font-display text-xl text-ink [font-variation-settings:'SOFT'_100]">Activity</h2>
        {alerts.supported ? (
          <button
            type="button"
            onClick={() => alerts.set(!alerts.enabled)}
            aria-pressed={alerts.enabled}
            className="rounded-full px-3 py-1 text-xs text-ink-dim ring-1 ring-white/12 transition hover:text-ink aria-pressed:text-tone aria-pressed:ring-tone/40"
          >
            Desktop alerts {alerts.enabled ? "on" : "off"}
          </button>
        ) : null}
      </div>

      {events.length === 0 ? (
        <p className="mt-4 text-sm leading-relaxed text-ink-faint">
          Nothing to report. Changes in how the baby is doing will appear here.
        </p>
      ) : (
        <ol className="mt-4 flex flex-col gap-3">
          {events.slice(0, 8).map((e) => (
            <li key={e.id} className="rise flex items-start gap-3 text-sm">
              <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: TONE_HEX[e.tone] }} aria-hidden />
              <span className="flex-1 text-ink">{e.text}</span>
              <time className="shrink-0 tabular-nums text-ink-faint" dateTime={new Date(e.at).toISOString()}>
                {time(e.at)}
              </time>
            </li>
          ))}
        </ol>
      )}

      {!alerts.supported && (
        <p className="mt-4 text-xs leading-relaxed text-ink-faint">
          Desktop alerts need a secure connection (https, or localhost).
        </p>
      )}
    </section>
  );
}
