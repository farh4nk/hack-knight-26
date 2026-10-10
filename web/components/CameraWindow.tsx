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
  const { latest, stale, sourceMode, setSourceMode } = useTelemetry();
  const daemon = useDaemonUrl();
  const [offline, setOffline] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [overlay, setOverlay] = useState(false);
  const [privacyBlur, setPrivacyBlur] = useState(false);
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
    <section className="flex flex-col gap-3">
      {/* Vitals Mode Toggle Switch */}
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-2xl bg-white/5 p-2 px-3.5 ring-1 ring-white/10 text-xs">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-ink-dim">Telemetry Sensor:</span>
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-medium ${
              sourceMode === "REALTIME"
                ? "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30"
                : "bg-tone/15 text-tone ring-1 ring-tone/30"
            }`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                sourceMode === "REALTIME" ? "bg-emerald-400" : "bg-tone"
              } animate-pulse`}
            />
            {sourceMode === "REALTIME" ? "Live Optical Sensor" : "Simulated Demo"}
          </span>
        </div>

        <div className="flex items-center rounded-xl bg-black/40 p-0.5 ring-1 ring-white/10">
          <button
            type="button"
            onClick={() => setSourceMode("mock")}
            className={`rounded-lg px-2.5 py-1 text-xs transition ${
              sourceMode === "SIMULATED"
                ? "bg-tone text-[#0a0b15] font-semibold shadow-sm"
                : "text-ink-dim hover:text-ink"
            }`}
          >
            ⚡ Simulated
          </button>
          <button
            type="button"
            onClick={() => setSourceMode("real")}
            className={`rounded-lg px-2.5 py-1 text-xs transition ${
              sourceMode === "REALTIME"
                ? "bg-emerald-400 text-[#0a0b15] font-semibold shadow-sm"
                : "text-ink-dim hover:text-ink"
            }`}
          >
            🎥 Real-Time Camera
          </button>
        </div>
      </div>
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
              className={`h-full w-full object-cover transition-all duration-700 ${
                privacyBlur ? "scale-105 blur-2xl opacity-40 brightness-75" : ""
              }`}
              // The load can fail before hydration, in which case onError never fires.
              ref={(el) => {
                if (el?.complete && el.naturalWidth === 0) setOffline(true);
              }}
              onError={() => setOffline(true)}
            />
          )}

          {/* Privacy Shield Blur Overlay */}
          {privacyBlur && !offline && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-black/40 text-center text-ink backdrop-blur-sm pointer-events-none p-4">
              <svg className="h-9 w-9 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
              <span className="font-display text-lg text-ink [font-variation-settings:'SOFT'_100]">
                Privacy Shield Active
              </span>
              <span className="max-w-xs text-xs text-ink-dim">
                Video obscured · Biometrics & auto-soothe actively running on local device
              </span>
            </div>
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
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setPrivacyBlur((b) => !b)}
            aria-pressed={privacyBlur}
            className={`flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs transition ${
              privacyBlur
                ? "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30"
                : "hover:text-ink"
            }`}
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
            {privacyBlur ? "Privacy blur: ON" : "Privacy blur"}
          </button>
          <button
            type="button"
            onClick={() => setOverlay((o) => !o)}
            aria-pressed={overlay}
            className="rounded-full px-2 py-0.5 underline-offset-4 transition hover:text-ink hover:underline aria-pressed:text-tone"
          >
            {overlay ? "Hide" : "Show"} detection overlay
          </button>
        </div>
      </div>
    </section>
  );
}
