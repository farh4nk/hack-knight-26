"use client";

import { useEffect, useState } from "react";
import { useTelemetry } from "@/context/TelemetryProvider";
import type { CameraStatus, NightVisionMode } from "@/lib/types";
import { useDaemonUrl } from "@/lib/useDaemonUrl";
import { hasSeparateEdge, nightVisionUrl } from "@/lib/config";
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

const NIGHT_VISION_MODES: NightVisionMode[] = ["OFF", "AUTO", "ON"];
const NIGHT_VISION_LABELS: Record<NightVisionMode, string> = {
  OFF: "Off",
  AUTO: "Auto",
  ON: "On",
};

/** The live feed, framed like a window and lit by the baby's current state. */
export function CameraWindow() {
  const { latest, stale, setCameraEnabled, sourceMode, setSourceMode } = useTelemetry();
  const daemon = useDaemonUrl();
  const [offline, setOffline] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [overlay, setOverlay] = useState(false);
  const [privacyBlur, setPrivacyBlur] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [toggleError, setToggleError] = useState<string | null>(null);
  const feedUrl = daemon ? `${daemon}${overlay ? "/video_feed/debug" : "/video_feed"}` : null;
  const camera = stale ? undefined : latest?.camera;
  const cameraOff = camera?.enabled === false;

  const toggleCamera = async () => {
    setToggling(true);
    setToggleError(null);
    try {
      await setCameraEnabled(cameraOff);
    } catch (e) {
      setToggleError(e instanceof Error ? e.message : "Couldn’t reach the camera unit.");
    } finally {
      setToggling(false);
    }
  };

  // While offline, re-request the MJPEG stream every few seconds.
  useEffect(() => {
    if (!offline) return;
    const timer = setTimeout(() => {
      setOffline(false);
      setAttempt((n) => n + 1);
    }, RETRY_MS);
    return () => clearTimeout(timer);
  }, [offline]);

  // With a separate edge unit the daemon only sees the edge's stream, so its telemetry can't say
  // what the edge's night vision is doing: read the mode from the edge itself.
  const [edgeMode, setEdgeMode] = useState<NightVisionMode | null>(null);
  useEffect(() => {
    if (!daemon || !hasSeparateEdge()) return;
    const load = () =>
      fetch(nightVisionUrl())
        .then((r) => (r.ok ? r.json() : null))
        .then((j) => j && setEdgeMode(j.mode))
        .catch(() => {});
    load();
    const timer = setInterval(load, 5000);
    return () => clearInterval(timer);
  }, [daemon]);
  const currentMode = (hasSeparateEdge() ? edgeMode : camera?.night_vision) ?? "OFF";
  const setNightVision = async (mode: NightVisionMode) => {
    if (!daemon) return;
    try {
      const res = await fetch(nightVisionUrl(), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode }),
      });
      if (res.ok && hasSeparateEdge()) setEdgeMode((await res.json()).mode);
    } catch {
      // Non-blocking; daemon will push updated state via telemetry
    }
  };

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
          {/* Not loaded while the camera is off: no stream requests, no stale frames. */}
          {!cameraOff && !offline && feedUrl && (
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

          {/* Low-light enhanced indicator */}
          {camera?.enhancing && !offline && !cameraOff && (
            <div className="absolute right-3 top-3 z-10">
              <span className="flex items-center gap-1 rounded-full bg-emerald-500/20 px-2.5 py-1 text-xs text-emerald-300 ring-1 ring-emerald-500/30">
                <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
                Low-light enhanced
              </span>
            </div>
          )}

          {cameraOff && sourceMode === "SIMULATED" && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 px-6 text-center select-none">
              {/* Animated Nursery Soundwave / Breath wave */}
              <div className="flex items-center justify-center gap-1.5 py-1">
                {[0.35, 0.6, 0.9, 0.75, 0.5, 0.85, 1.0, 0.7, 0.45, 0.8, 0.95, 0.6, 0.5, 0.75, 0.4, 0.55].map((scale, i) => (
                  <div
                    key={i}
                    className="w-1.5 rounded-full transition-all duration-500 ease-in-out"
                    style={{
                      height: `${Math.round(16 + scale * 30)}px`,
                      backgroundColor: "var(--tone)",
                      opacity: 0.6 + scale * 0.4,
                      animation: `pulse ${1.6 + (i % 5) * 0.25}s ease-in-out infinite alternate`,
                    }}
                  />
                ))}
              </div>

              <div className="flex items-center gap-2 rounded-full bg-tone/15 px-3 py-1 text-xs font-medium text-tone ring-1 ring-tone/30">
                <span className="h-1.5 w-1.5 rounded-full bg-tone animate-ping" />
                Synthetic Vitals Active · Camera Off
              </div>

              <div className="flex flex-col items-center gap-1">
                <span className="font-display text-2xl text-ink [font-variation-settings:'SOFT'_100]">
                  Simulated Nursery Monitor
                </span>
                <span className="max-w-md text-xs text-ink-dim">
                  Camera feed is off · Continuous pediatric vitals and sleep cycle simulation stream
                </span>
              </div>

              {/* Vitals snapshot */}
              <div className="flex items-center gap-3 rounded-full bg-black/40 px-4 py-1.5 text-xs text-ink-dim ring-1 ring-white/10 font-mono">
                <span>
                  <strong className="text-tone font-semibold">{latest?.vitals.brpm ?? 24}</strong> BrPM
                </span>
                <span className="text-white/20">·</span>
                <span>
                  <strong className="text-tone font-semibold">{latest?.vitals.bpm ?? 115}</strong> BPM
                </span>
                <span className="text-white/20">·</span>
                <span>
                  <strong className="text-emerald-400 font-semibold">{Math.round((latest?.vitals.confidence ?? 0.9) * 100)}%</strong> Conf
                </span>
              </div>

              <button
                type="button"
                onClick={toggleCamera}
                disabled={toggling}
                className="mt-1 rounded-full bg-white/10 px-4 py-1.5 text-xs font-medium text-ink ring-1 ring-white/15 transition hover:bg-white/20 disabled:opacity-50"
              >
                {toggling ? "Turning on…" : "Turn camera on"}
              </button>
            </div>
          )}

          {cameraOff && sourceMode === "REALTIME" && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 px-6 text-center">
              <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className="text-ink-faint" aria-hidden>
                <path d="M2 2l20 20" />
                <path d="M7 7H5a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h11a2 2 0 0 0 1.4-.6" />
                <path d="M21 17V8.4a1 1 0 0 0-1.6-.8L16 10V9a2 2 0 0 0-2-2h-3" />
              </svg>
              <span className="font-display text-2xl text-ink [font-variation-settings:'SOFT'_100]">Camera is off</span>
              <span className="max-w-sm text-sm text-ink-dim">
                Monitoring is paused. Presage isn’t running, so no credits are being used.
              </span>
              <button
                type="button"
                onClick={toggleCamera}
                disabled={toggling}
                className="mt-1 rounded-full bg-ink px-5 py-2 text-sm font-medium text-[#0a0b15] transition hover:opacity-90 disabled:opacity-50"
              >
                {toggling ? "Turning on…" : "Turn camera on"}
              </button>
            </div>
          )}

          {/* Privacy Shield Blur Overlay */}
          {privacyBlur && !offline && !cameraOff && (
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

          {offline && !cameraOff && (
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
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <button
            type="button"
            role="switch"
            aria-checked={!cameraOff}
            aria-label="Camera"
            onClick={toggleCamera}
            // Unknown state (no telemetry yet / daemon unreachable): don't guess which way to flip.
            disabled={toggling || !camera}
            className="flex items-center gap-2 rounded-full py-0.5 pl-0.5 pr-3 text-xs text-ink-dim ring-1 ring-white/12 transition hover:text-ink disabled:cursor-not-allowed disabled:opacity-50"
          >
            <span className={`relative h-5 w-9 rounded-full transition-colors ${cameraOff ? "bg-white/15" : "bg-tone"}`}>
              <span
                className={`absolute top-0.5 h-4 w-4 rounded-full bg-ink shadow transition-all ${cameraOff ? "left-0.5" : "left-[1.125rem]"}`}
              />
            </span>
            Camera {toggling ? "…" : cameraOff ? "off" : "on"}
          </button>
          <span className="flex flex-wrap items-center">
            {cameraOff
              ? sourceMode === "SIMULATED"
                ? "Camera off · Synthetic vitals active"
                : "Presage paused · no credits in use"
              : camera
                ? statusParts(camera).map((part, i) => (
                    <span key={part} className="flex items-center">
                      {i > 0 && <span aria-hidden className="mx-2.5 text-ink-faint/60">·</span>}
                      {part}
                    </span>
                  ))
                : " "}
          </span>
        </div>
        {!cameraOff && (
          <div className="flex items-center gap-3">
              {/* Night Vision segmented control */}
              <div className="flex items-center gap-1 rounded-full bg-white/5 p-0.5 ring-1 ring-white/10" role="group" aria-label="Night vision">
                {NIGHT_VISION_MODES.map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    onClick={() => setNightVision(mode)}
                    aria-pressed={currentMode === mode}
                    className={`flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs transition ${
                      currentMode === mode
                        ? "bg-white/15 text-ink"
                        : "text-ink-dim hover:text-ink"
                    }`}
                  >
                    {NIGHT_VISION_LABELS[mode]}
                  </button>
                ))}
              </div>
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
        )}
      </div>
      {toggleError && (
        <p role="alert" className="px-2 text-sm text-rose-300">
          {toggleError}
        </p>
      )}
    </section>
  );
}
