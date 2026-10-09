"use client";

import { useEffect, useState } from "react";
import { SootheEngine, SootheSnapshot } from "@/lib/audio/soothe-engine";
import { synthesize } from "@/lib/audio/elevenlabs";

interface SootheControlsProps {
  engine: SootheEngine;
  snapshot: SootheSnapshot;
  voiceId: string;
  onChangeVoice?: () => void;
}

const STATUS_LABELS: Record<string, { text: string; color: string }> = {
  idle: { text: "Auto-Soothe Primed & Ready", color: "text-emerald-400" },
  pending: { text: "Restlessness detected (4s gate)…", color: "text-amber-400" },
  soothing: { text: "Soothing in your voice", color: "text-indigo-400" },
  fading: { text: "Settled — smoothly fading audio", color: "text-sky-400" },
};

export function SootheControls({ engine, snapshot, voiceId, onChangeVoice }: SootheControlsProps) {
  const [now, setNow] = useState(() => Date.now());
  const [customText, setCustomText] = useState("");
  const [talking, setTalking] = useState(false);

  const locked = snapshot.cooldownUntil > now;
  const active = snapshot.status === "soothing" || snapshot.status === "fading";

  useEffect(() => {
    if (!locked) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [locked]);

  const minsLeft = Math.ceil((snapshot.cooldownUntil - now) / 60000);
  const statusInfo = STATUS_LABELS[snapshot.status] || STATUS_LABELS.idle;

  const handleTalkToBaby = async () => {
    if (!customText.trim() || talking) return;
    setTalking(true);
    try {
      const url = await synthesize(voiceId, customText.trim());
      await engine.playOnce(url);
      setCustomText("");
    } catch (e) {
      console.error("Talk to baby error:", e);
    } finally {
      setTalking(false);
    }
  };

  return (
    <div className="rounded-2xl bg-slate-900 p-5 ring-1 ring-white/10">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-slate-400">Auto-Soothe Pipeline</span>
        <label className="flex cursor-pointer items-center gap-2 text-xs font-medium text-slate-300">
          <input
            type="checkbox"
            checked={snapshot.enabled}
            onChange={(e) => {
              if (e.target.checked) engine.unlock();
              engine.setEnabled(e.target.checked);
            }}
            className="h-4 w-4 rounded border-slate-700 bg-slate-800 text-indigo-600 focus:ring-indigo-500"
          />
          Enabled
        </label>
      </div>

      {/* State Badge */}
      <div className="mt-3 flex items-center justify-between rounded-xl bg-slate-800/80 p-3">
        <div>
          <div className={`text-xs font-semibold ${statusInfo.color}`}>
            {snapshot.enabled ? statusInfo.text : "Auto-Soothe Disabled"}
          </div>
          {snapshot.snippet && active && (
            <div className="mt-1 text-xs italic text-slate-300">
              “{snapshot.snippet}”
            </div>
          )}
        </div>
      </div>

      {/* Lockout / Cooldown Indicator (Task 3.4) */}
      {locked && !active && (
        <div className="mt-2 flex items-center justify-between rounded-lg bg-amber-500/10 px-3 py-1.5 text-xs text-amber-400">
          <span>Lockout: paused for {minsLeft}m to prevent infinite soothing</span>
          <button
            type="button"
            onClick={() => engine.resetCooldown()}
            className="font-medium underline hover:text-amber-300"
          >
            Reset
          </button>
        </div>
      )}

      {/* Instant Mute / Stop Soothe (Task 3.4) */}
      <div className="mt-3">
        <button
          type="button"
          onClick={() => engine.stop()}
          disabled={!active && snapshot.status !== "pending"}
          className="w-full rounded-xl bg-rose-600 px-4 py-2.5 text-xs font-semibold text-white transition hover:bg-rose-500 disabled:cursor-not-allowed disabled:bg-slate-800 disabled:text-slate-600"
        >
          Mute / Stop Soothe
        </button>
      </div>

      {/* Talk to Baby Live TTS */}
      <div className="mt-4 border-t border-white/5 pt-3">
        <span className="text-xs font-medium text-slate-400">Talk to Maya (Cloned Voice)</span>
        <div className="mt-1.5 flex gap-2">
          <input
            type="text"
            value={customText}
            onChange={(e) => setCustomText(e.target.value)}
            placeholder="Type soothing words…"
            className="flex-1 rounded-lg border border-white/10 bg-slate-800 px-3 py-1.5 text-xs text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
            onKeyDown={(e) => e.key === "Enter" && handleTalkToBaby()}
          />
          <button
            type="button"
            onClick={handleTalkToBaby}
            disabled={!customText.trim() || talking}
            className="rounded-lg bg-slate-800 px-3 py-1.5 text-xs font-medium text-indigo-400 hover:bg-slate-700 disabled:opacity-50"
          >
            {talking ? "Speaking…" : "Speak"}
          </button>
        </div>
      </div>

      {onChangeVoice && (
        <button
          type="button"
          onClick={onChangeVoice}
          className="mt-3 block text-center text-xs text-slate-500 underline hover:text-slate-400"
        >
          Re-record Parent Voice
        </button>
      )}
    </div>
  );
}
