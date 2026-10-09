"use client";

import { useEffect, useState } from "react";
import { VIDEO_FEED_URL } from "@/lib/config";
import { StateBadge } from "./StateBadge";

const RETRY_MS = 3000;

export function StreamCard() {
  const [offline, setOffline] = useState(false);
  const [attempt, setAttempt] = useState(0);

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
    <section className="relative aspect-video w-full overflow-hidden rounded-2xl bg-slate-900 ring-1 ring-white/10">
      {!offline && (
        // MJPEG stream: plain <img>, next/image can't handle multipart streams.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          key={attempt}
          src={`${VIDEO_FEED_URL}?attempt=${attempt}`}
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
          <span className="text-sm">Retrying {VIDEO_FEED_URL}…</span>
        </div>
      )}
      <div className="absolute inset-x-0 top-0 flex justify-center p-4">
        <StateBadge />
      </div>
    </section>
  );
}
