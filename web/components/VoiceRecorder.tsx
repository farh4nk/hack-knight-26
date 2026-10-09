"use client";

import { useEffect, useRef, useState } from "react";

const RECORD_SECONDS = 10;

interface VoiceRecorderProps {
  onComplete: (sample: Blob) => Promise<void>;
  loading?: boolean;
}

export function VoiceRecorder({ onComplete, loading }: VoiceRecorderProps) {
  const [phase, setPhase] = useState<"idle" | "recording" | "uploading" | "done" | "error">("idle");
  const [remaining, setRemaining] = useState(RECORD_SECONDS);
  const [error, setError] = useState<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => {
      if (tickRef.current) clearInterval(tickRef.current);
      recorderRef.current?.stream.getTracks().forEach((t) => t.stop());
    };
  }, []);

  async function start() {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const chunks: Blob[] = [];
      const rec = new MediaRecorder(stream);
      recorderRef.current = rec;

      rec.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.push(e.data);
      };

      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        if (tickRef.current) clearInterval(tickRef.current);
        setPhase("uploading");
        try {
          await onComplete(new Blob(chunks, { type: rec.mimeType || "audio/webm" }));
          setPhase("done");
        } catch (e) {
          setError(e instanceof Error ? e.message : "Upload failed");
          setPhase("error");
        }
      };

      rec.start();
      setRemaining(RECORD_SECONDS);
      setPhase("recording");

      const startedAt = Date.now();
      tickRef.current = setInterval(() => {
        const left = Math.max(0, RECORD_SECONDS - Math.floor((Date.now() - startedAt) / 1000));
        setRemaining(left);
        if (left === 0 && rec.state === "recording") rec.stop();
      }, 250);
    } catch {
      setError("Microphone access was blocked. Please allow mic permissions in your browser.");
      setPhase("error");
    }
  }

  return (
    <div className="rounded-2xl bg-slate-900 p-5 ring-1 ring-white/10">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-slate-400">Parent Voice Onboarding</span>
        <span className="rounded bg-indigo-950 px-2 py-0.5 text-xs text-indigo-400">ElevenLabs IVC</span>
      </div>

      <p className="mt-2 text-xs text-slate-400">
        Record your voice for {RECORD_SECONDS} seconds in a calm, soothing tone. CradleEcho uses
        your voice clone to settle Maya before you have to get out of bed.
      </p>

      {phase === "recording" && (
        <div className="mt-3 flex items-center gap-2 rounded-lg bg-rose-500/10 px-3 py-2 text-sm text-rose-400">
          <span className="inline-block h-2.5 w-2.5 animate-ping rounded-full bg-rose-500" />
          Recording… {remaining}s remaining
        </div>
      )}

      {(phase === "uploading" || loading) && (
        <div className="mt-3 flex items-center gap-2 text-sm text-indigo-400">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-indigo-400 border-t-transparent" />
          Creating instant voice clone…
        </div>
      )}

      {error && <p className="mt-2 text-xs text-rose-400">{error}</p>}

      <button
        type="button"
        onClick={start}
        disabled={phase === "recording" || phase === "uploading" || loading}
        className="mt-3 w-full rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
      >
        {phase === "done" ? "Re-record Voice" : "Record 10-Sec Sample"}
      </button>
    </div>
  );
}
