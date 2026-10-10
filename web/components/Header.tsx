"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTelemetry } from "@/context/TelemetryProvider";
import { APP_NAME } from "@/lib/config";
import { useDaemonUrl } from "@/lib/useDaemonUrl";

export function Header() {
  const pathname = usePathname();
  const { connected, stale, mock } = useTelemetry();
  const daemon = useDaemonUrl();
  const live = connected && !stale;

  return (
    <header className="flex flex-wrap items-center justify-between gap-4 py-7">
      <div className="flex items-center gap-6">
        <Link href="/" className="flex items-center gap-3 transition hover:opacity-85">
          {/* Crescent moon, tinted by current state */}
          <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden className="text-tone transition-colors duration-1000">
            <path
              fill="currentColor"
              d="M20.5 14.2A8.5 8.5 0 0 1 9.8 3.5a.6.6 0 0 0-.8-.7A10 10 0 1 0 21.2 15a.6.6 0 0 0-.7-.8Z"
            />
          </svg>
          <span className="font-display text-xl tracking-tight text-ink [font-variation-settings:'SOFT'_100]">
            {APP_NAME}
          </span>
        </Link>

        {/* Navigation pill tabs */}
        <nav className="flex items-center gap-1 rounded-full bg-white/5 p-1 ring-1 ring-white/10">
          <Link
            href="/"
            className={`rounded-full px-3.5 py-1 text-xs font-medium transition ${
              pathname === "/"
                ? "bg-white/15 text-ink shadow-sm"
                : "text-ink-dim hover:text-ink hover:bg-white/5"
            }`}
          >
            Live Monitor
          </Link>
          <Link
            href="/dashboard"
            className={`rounded-full px-3.5 py-1 text-xs font-medium transition ${
              pathname === "/dashboard"
                ? "bg-white/15 text-ink shadow-sm"
                : "text-ink-dim hover:text-ink hover:bg-white/5"
            }`}
          >
            Night Dashboard
          </Link>
        </nav>
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
