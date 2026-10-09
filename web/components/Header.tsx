"use client";

import { useTelemetry } from "@/context/TelemetryProvider";
import { APP_NAME } from "@/lib/config";
import { useDaemonUrl } from "@/lib/useDaemonUrl";

export function Header() {
  const { connected, stale, mock } = useTelemetry();
  const live = connected && !stale;
  const daemon = useDaemonUrl() ?? "";

  return (
    <header className="flex items-center justify-between py-6">
      <h1 className="text-xl font-semibold tracking-tight text-white">{APP_NAME}</h1>
      <div className="flex items-center gap-2 text-sm text-slate-400">
        <span className={`h-2.5 w-2.5 rounded-full ${live ? "bg-emerald-400" : "bg-slate-600"}`} />
        {mock ? "Mock telemetry" : live ? `Live · ${daemon}` : `Connecting to ${daemon}…`}
      </div>
    </header>
  );
}
