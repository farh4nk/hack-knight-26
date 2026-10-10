"use client";

import type { ReactNode } from "react";
import { useTelemetry } from "@/context/TelemetryProvider";
import { toneOf } from "@/lib/stateCopy";

/** Sets the baby's state as a data attribute so everything inside can use --tone, and draws the glow. */
export function NightShell({ children }: { children: ReactNode }) {
  const { latest, connected, stale } = useTelemetry();
  const tone = toneOf(latest, !connected || stale);

  return (
    <div data-state={tone} className="night relative isolate flex min-h-full flex-1 flex-col">
      <div aria-hidden className="night-glow pointer-events-none fixed inset-0 -z-10" />
      {children}
    </div>
  );
}
