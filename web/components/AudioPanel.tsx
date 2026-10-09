"use client";

import { useState } from "react";
import { useTelemetry } from "@/context/TelemetryProvider";
import { useVoiceProfile } from "@/hooks/useVoiceProfile";
import { useAutoSoothe } from "@/hooks/useAutoSoothe";
import { VoiceRecorder } from "./VoiceRecorder";
import { SootheControls } from "./SootheControls";
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
        setNotification(`Auto-soothe triggered: soothing Maya in your voice.`);
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
        setNotification(`Maya is settled and asleep. Audio smoothly faded out.`);
        setTimeout(() => setNotification(null), 8000);
      } else if (e.type === "stopped") {
        setNotification(null);
      }
    },
  });

  return (
    <div className="flex flex-col gap-3">
      {/* Active Intervention Banner for Parent */}
      {notification && (
        <div className="flex items-center justify-between rounded-xl border border-indigo-500/20 bg-indigo-950/60 p-3 text-xs text-indigo-300">
          <div className="flex items-center gap-2">
            <span className="inline-block h-2 w-2 animate-ping rounded-full bg-indigo-400" />
            <span>{notification}</span>
          </div>
          <button
            type="button"
            onClick={() => setNotification(null)}
            className="text-slate-400 hover:text-white"
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
            <div className="rounded-2xl bg-slate-900 p-4 text-center text-xs text-slate-400 ring-1 ring-white/10">
              Generating pre-rendered soothing phrases in cloned voice…
            </div>
          )}
          {error && (
            <div className="rounded-2xl bg-slate-900 p-4 text-xs text-rose-400 ring-1 ring-white/10">
              {error}
            </div>
          )}
          <SootheControls
            engine={engine}
            snapshot={snapshot}
            voiceId={voiceId}
            onChangeVoice={reset}
          />
        </>
      )}
    </div>
  );
}
