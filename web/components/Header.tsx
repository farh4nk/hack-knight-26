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

      <div className="flex items-center gap-3 text-sm text-ink-dim">
        {/* Local Edge Privacy Guard Badge */}
        <div
          title="Privacy Shield: Crib video is processed 100% locally on-device. Zero video frames uploaded to the cloud."
          className="hidden sm:flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2.5 py-1 text-xs text-emerald-400 ring-1 ring-emerald-500/25"
        >
          <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
          </svg>
          <span>Local Edge Guard</span>
        </div>

        <div className="flex items-center gap-2">
          <span
            className={`h-2 w-2 rounded-full ${live ? "bg-tone" : "bg-ink-faint"} ${live ? "breathe" : ""}`}
            aria-hidden
          />
          <span>
            {mock ? "Demo data" : live ? "Nursery · live" : "Connecting…"}
            {!mock && daemon ? <span className="hidden text-ink-faint sm:inline"> · {daemon.replace(/^https?:\/\//, "")}</span> : null}
          </span>
        </div>
      </div>
    </header>
  );
}
