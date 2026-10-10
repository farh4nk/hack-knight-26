"use client";

import { useState } from "react";
import { useTelemetry } from "@/context/TelemetryProvider";
import { useVoiceProfile } from "@/hooks/useVoiceProfile";
import { useAutoSoothe } from "@/hooks/useAutoSoothe";
import { VoiceRecorder } from "./VoiceRecorder";
import { SootheControls } from "./SootheControls";
import { babyObject, babySubject, getBabyName } from "@/lib/babyName";
import { analyticsUrl } from "@/lib/config";


export function AudioPanel() {
  const { latest } = useTelemetry();
  const state = latest?.state;

  const { voiceId, snippets, loading, error, onboard, reset } = useVoiceProfile();
  const [notification, setNotification] = useState<string | null>(null);

  const { engine, snapshot } = useAutoSoothe(state, snippets, {
    onEvent: async (e) => {
      console.info("[auto-soothe event]", e);
      if (e.type === "started") {
        setNotification(`Auto-soothe triggered: soothing ${babyObject(getBabyName())} in your voice.`);
        // Log intervention to Tiger Data via Dev 4 backend
        try {
          await fetch(`${analyticsUrl()}/api/soothe-events`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              triggered_at: new Date(e.at).toISOString(),
              voice_snippet_used: e.snippet || "Auto-soothe calming phrase",
              was_successful: true,
            }),
          });
        } catch {
          // Non-blocking if backend is offline
        }
      } else if (e.type === "settled") {
        setNotification(`${babySubject(getBabyName())} is settled and asleep. Audio smoothly faded out.`);
        setTimeout(() => setNotification(null), 8000);
      } else if (e.type === "stopped") {
        setNotification(null);
      }
    },
  });

  return (
    <section className="flex flex-col gap-4">
      {/* Shown to the parent whenever auto-soothe steps in or settles */}
      {notification && (
        <div role="status" className="rise flex items-center justify-between gap-3 rounded-2xl bg-white/5 px-4 py-3 text-sm text-ink ring-1 ring-tone/30">
          <div className="flex items-center gap-2.5">
            <span className="breathe h-2 w-2 shrink-0 rounded-full bg-tone" aria-hidden />
            <span>{notification}</span>
          </div>
          <button
            type="button"
            onClick={() => setNotification(null)}
            aria-label="Dismiss"
            className="text-ink-faint transition hover:text-ink"
          >
            ✕
          </button>
        </div>
      )}

      {!voiceId ? (
        <VoiceRecorder onComplete={onboard} loading={loading} />
      ) : (
        <>
          {snippets.length === 0 && !error && (
            <p className="text-sm text-ink-faint">Preparing soothing phrases in your voice…</p>
          )}
          {error && <p className="text-sm text-rose-300">{error}</p>}
          <SootheControls engine={engine} snapshot={snapshot} voiceId={voiceId} onChangeVoice={reset} />
        </>
      )}
    </section>
  );
}
