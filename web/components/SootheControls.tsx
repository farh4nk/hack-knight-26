"use client";

import { useEffect, useState } from "react";
import { SootheEngine, SootheSnapshot } from "@/lib/audio/soothe-engine";
import { synthesize } from "@/lib/audio/elevenlabs";
import { babyObject, useBabyName } from "@/lib/babyName";
import { edgeSoothePlayUrl } from "@/lib/config";

interface SootheControlsProps {
  engine: SootheEngine;
  snapshot: SootheSnapshot;
  voiceId: string;
  onChangeVoice?: () => void;
}

const STATUS_LABELS: Record<string, string> = {
  idle: "Ready. It steps in if restlessness continues.",
  pending: "Restlessness noticed. Waiting a few seconds…",
  soothing: "Soothing in your voice",
  fading: "Settled. Fading out…",
};

export function SootheControls({ engine, snapshot, voiceId, onChangeVoice }: SootheControlsProps) {
  const [now, setNow] = useState(() => Date.now());
  const [customText, setCustomText] = useState("");
  const [talking, setTalking] = useState(false);
  const name = useBabyName() ?? "";

  const locked = snapshot.cooldownUntil > now;
  const active = snapshot.status === "soothing" || snapshot.status === "fading";

  useEffect(() => {
    if (!locked) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [locked]);

  const minsLeft = Math.ceil((snapshot.cooldownUntil - now) / 60000);
  const status = STATUS_LABELS[snapshot.status] ?? STATUS_LABELS.idle;

  const handleTalkToBaby = async () => {
    if (!customText.trim() || talking) return;
    setTalking(true);
    try {
      const url = await synthesize(voiceId, customText.trim());
      await engine.playOnce(url);
      try {
        fetch(edgeSoothePlayUrl(), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ phrase: customText.trim() }),
        }).catch(() => {});
      } catch {}
      setCustomText("");
    } catch (e) {
      console.error("Talk to baby error:", e);
    } finally {
      setTalking(false);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between">
        <h2 className="font-display text-xl text-ink [font-variation-settings:'SOFT'_100]">Auto-soothe</h2>
        <button
          type="button"
          role="switch"
          aria-checked={snapshot.enabled}
          aria-label="Auto-soothe"
          onClick={() => {
            if (!snapshot.enabled) engine.unlock();
            engine.setEnabled(!snapshot.enabled);
          }}
          className={`relative h-6 w-11 rounded-full transition-colors ${snapshot.enabled ? "bg-tone" : "bg-white/15"}`}
        >
          <span
            className={`absolute top-0.5 h-5 w-5 rounded-full bg-ink shadow transition-all ${snapshot.enabled ? "left-[1.375rem]" : "left-0.5"}`}
          />
        </button>
      </div>

      <p className="mt-3 text-sm text-ink-dim" role="status">
        {snapshot.enabled ? status : "Auto-soothe is off."}
      </p>
      {snapshot.snippet && active && (
        <p className="rise mt-2 font-display text-lg italic leading-snug text-ink [font-variation-settings:'SOFT'_100]">
          “{snapshot.snippet}”
        </p>
      )}

      {/* Cooldown lockout: stops it repeating if the baby is truly awake */}
      {locked && !active && (
        <p className="mt-3 text-sm text-ink-faint">
          Paused for {minsLeft} min so it doesn’t repeat.{" "}
          <button type="button" onClick={() => engine.resetCooldown()} className="underline underline-offset-4 hover:text-ink">
            Reset
          </button>
        </p>
      )}

      <button
        type="button"
        onClick={() => engine.stop()}
        disabled={!active && snapshot.status !== "pending"}
        className="mt-4 w-full rounded-full px-4 py-2.5 text-sm text-rose-200 ring-1 ring-rose-300/35 transition hover:bg-rose-300/10 disabled:cursor-not-allowed disabled:text-ink-faint disabled:ring-white/10 disabled:hover:bg-transparent"
      >
        Mute / stop soothing
      </button>

      <div className="mt-6 border-t border-line pt-5">
        <label htmlFor="talk" className="text-sm text-ink-dim">
          Say something to {babyObject(name)}, in your voice
        </label>
        <div className="mt-2 flex gap-2">
          <input
            id="talk"
            type="text"
            value={customText}
            onChange={(e) => setCustomText(e.target.value)}
            placeholder="Shh, I’m right here…"
            className="min-w-0 flex-1 rounded-xl bg-white/5 px-3.5 py-2 text-sm text-ink placeholder:text-ink-faint ring-1 ring-white/10 focus:outline-none focus:ring-tone/50"
            onKeyDown={(e) => e.key === "Enter" && handleTalkToBaby()}
          />
          <button
            type="button"
            onClick={handleTalkToBaby}
            disabled={!customText.trim() || talking}
            className="rounded-xl bg-ink px-4 py-2 text-sm font-medium text-[#0a0b15] transition hover:opacity-90 disabled:opacity-40"
          >
            {talking ? "Speaking…" : "Speak"}
          </button>
        </div>
      </div>

      {onChangeVoice && (
        <button
          type="button"
          onClick={onChangeVoice}
          className="mt-4 text-sm text-ink-faint underline underline-offset-4 transition hover:text-ink"
        >
          Re-record my voice
        </button>
      )}
      <p className="mt-5 text-xs text-ink-faint">Voice by ElevenLabs</p>
    </div>
  );
}
