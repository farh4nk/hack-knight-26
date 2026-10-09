"use client";

import { useEffect, useState } from "react";
import { useTelemetry } from "@/context/TelemetryProvider";
import { FRAMING_LABELS } from "@/lib/cameraHint";
import { useDaemonUrl } from "@/lib/useDaemonUrl";
import { StateBadge } from "./StateBadge";

const RETRY_MS = 3000;

export function StreamCard() {
  const [offline, setOffline] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [debug, setDebug] = useState(false);
  const daemon = useDaemonUrl();
  const feedUrl = daemon ? `${daemon}${debug ? "/video_feed/debug" : "/video_feed"}` : null;

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
      <div className="relative aspect-video w-full overflow-hidden rounded-2xl bg-slate-900 ring-1 ring-white/10">
        {!offline && feedUrl && (
          // MJPEG stream: plain <img>, next/image can't handle multipart streams.
          // eslint-disable-next-line @next/next/no-img-element
          <img
            key={`${feedUrl}-${attempt}`}
            src={`${feedUrl}?attempt=${attempt}`}
            alt="Live crib camera"
            className="h-full w-full object-cover"
            // The load can fail before hydration, in which case onError never fires.
            ref={(el) => {
              if (el?.complete && el.naturalWidth === 0) setOffline(true);
            }}
            onError={() => setOffline(true)}
          />
        )}
        {offline && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-slate-400">
            <span className="text-lg font-medium">Camera offline</span>
            <span className="text-sm">Retrying {feedUrl}…</span>
          </div>
        )}
        <div className="absolute inset-x-0 top-0 flex justify-center p-4">
          <StateBadge />
        </div>
      </div>
      <CameraStatusBar debug={debug} onToggleDebug={() => setDebug((d) => !d)} />
    </section>
  );
}

function CameraStatusBar({ debug, onToggleDebug }: { debug: boolean; onToggleDebug: () => void }) {
  const { latest, stale } = useTelemetry();
  const camera = stale ? undefined : latest?.camera;

  const chips = camera
    ? [
        camera.live
          ? { text: "Camera live", tone: "ok" as const }
          : { text: "Synthetic feed", tone: "warn" as const },
        camera.gate === "OPEN"
          ? { text: "Presage running", tone: "ok" as const }
          : camera.gate === "CLOSED"
            ? { text: "Presage idle", tone: "muted" as const }
            : { text: "Face gate off", tone: "muted" as const },
        {
          text: FRAMING_LABELS[camera.framing] ?? camera.framing,
          tone: camera.framing === "OK" ? ("ok" as const) : ("warn" as const),
        },
      ]
    : [];

  const toneClass = {
    ok: "bg-emerald-500/15 text-emerald-300",
    warn: "bg-amber-500/15 text-amber-300",
    muted: "bg-slate-800 text-slate-400",
  };

  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <div className="flex flex-wrap gap-2 text-xs font-medium">
        {chips.map((c) => (
          <span key={c.text} className={`rounded-full px-2.5 py-1 ${toneClass[c.tone]}`}>
            {c.text}
          </span>
        ))}
      </div>
      <button
        type="button"
        onClick={onToggleDebug}
        aria-pressed={debug}
        className={`rounded-full px-3 py-1 text-xs font-medium ring-1 transition ${
          debug
            ? "bg-sky-500/20 text-sky-300 ring-sky-400/40"
            : "text-slate-400 ring-white/10 hover:text-slate-200"
        }`}
      >
        Debug overlay {debug ? "on" : "off"}
      </button>
    </div>
  );
}
