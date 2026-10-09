"use client";

import { useTelemetry } from "@/context/TelemetryProvider";
import { APP_NAME } from "@/lib/config";
import { useDaemonUrl } from "@/lib/useDaemonUrl";

export function Header() {
  const { connected, stale, mock } = useTelemetry();
  const daemon = useDaemonUrl();
  const live = connected && !stale;

  return (
    <header className="flex items-center justify-between py-7">
      <div className="flex items-center gap-3">
        {/* Crescent moon, tinted by the current state */}
        <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden className="text-tone transition-colors duration-1000">
          <path
            fill="currentColor"
            d="M20.5 14.2A8.5 8.5 0 0 1 9.8 3.5a.6.6 0 0 0-.8-.7A10 10 0 1 0 21.2 15a.6.6 0 0 0-.7-.8Z"
          />
        </svg>
        <span className="font-display text-xl tracking-tight text-ink [font-variation-settings:'SOFT'_100]">
          {APP_NAME}
        </span>
      </div>
      <div className="flex items-center gap-2 text-sm text-ink-dim">
        <span
          className={`h-2 w-2 rounded-full ${live ? "bg-tone" : "bg-ink-faint"} ${live ? "breathe" : ""}`}
          aria-hidden
        />
        <span>
          {mock ? "Demo data" : live ? "Nursery · live" : "Connecting…"}
          {!mock && daemon ? <span className="hidden text-ink-faint sm:inline"> · {daemon.replace(/^https?:\/\//, "")}</span> : null}
        </span>
      </div>
    </header>
  );
}
