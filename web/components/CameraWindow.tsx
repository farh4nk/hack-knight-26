"use client";

import { useEffect, useState } from "react";
import { useTelemetry } from "@/context/TelemetryProvider";
import type { CameraStatus } from "@/lib/types";
import { useDaemonUrl } from "@/lib/useDaemonUrl";
import { StateBadge } from "./StateBadge";

const RETRY_MS = 3000;

function statusParts(camera: CameraStatus): string[] {
  const parts = [camera.live ? "Camera live" : "Placeholder feed (no camera)"];
  parts.push(
    camera.gate === "OPEN" ? "Reading vitals" : camera.gate === "CLOSED" ? "Waiting for a face" : "Face gate off",
  );
  if (camera.framing === "OK") parts.push("Framing good");
  return parts;
}

/** The live feed, framed like a window and lit by the baby's current state. */
export function CameraWindow() {
  const { latest, stale } = useTelemetry();
  const daemon = useDaemonUrl();
  const [offline, setOffline] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [overlay, setOverlay] = useState(false);
  const feedUrl = daemon ? `${daemon}${overlay ? "/video_feed/debug" : "/video_feed"}` : null;
  const camera = stale ? undefined : latest?.camera;

  // While offline, re-request the MJPEG stream every few seconds.
  useEffect(() => {
    if (!offline) return;
    const timer = setTimeout(() => {
      setOffline(false);
      setAttempt((n) => n + 1);
    }, RETRY_MS);
    return () => clearTimeout(timer);
  }, [offline]);

  return (
    <section className="flex flex-col gap-4">
      <div
        className="rounded-[2rem] p-1.5 ring-1 ring-white/10"
        style={{
          background: "linear-gradient(160deg, color-mix(in srgb, var(--tone) 38%, transparent), rgba(255,255,255,0.04) 55%)",
          boxShadow: "0 0 110px -30px var(--tone), 0 40px 80px -40px rgba(0,0,0,0.9)",
        }}
      >
        <div className="relative aspect-video overflow-hidden rounded-[1.6rem] bg-black/70">
          {!offline && feedUrl && (
            // MJPEG stream: plain <img>, next/image can't handle multipart streams.
            // eslint-disable-next-line @next/next/no-img-element
            <img
              key={`${feedUrl}-${attempt}`}
              src={`${feedUrl}?attempt=${attempt}`}
              alt="Live view of the crib"
              className="h-full w-full object-cover"
              // The load can fail before hydration, in which case onError never fires.
              ref={(el) => {
                if (el?.complete && el.naturalWidth === 0) setOffline(true);
              }}
              onError={() => setOffline(true)}
            />
          )}
          {offline && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-1 text-center text-ink-dim">
              <span className="font-display text-2xl text-ink">Camera offline</span>
              <span className="text-sm">Trying to reconnect…</span>
            </div>
          )}
          {/* Soft vignette so the picture sits inside the frame */}
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(120%_95%_at_50%_45%,transparent_58%,rgba(6,7,14,0.55))]" />
          <div className="absolute left-4 top-4">
            <StateBadge />
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 px-2 text-sm text-ink-faint">
        <span>{camera ? statusParts(camera).join("  ·  ") : " "}</span>
        <button
          type="button"
          onClick={() => setOverlay((o) => !o)}
          aria-pressed={overlay}
          className="rounded-full px-2 py-0.5 underline-offset-4 transition hover:text-ink hover:underline aria-pressed:text-tone"
        >
          {overlay ? "Hide" : "Show"} detection overlay
        </button>
      </div>
    </section>
  );
}
