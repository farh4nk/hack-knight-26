"use client";

import { useEffect, useRef, useState } from "react";
import { babyObject, useBabyName } from "@/lib/babyName";

const RECORD_SECONDS = 10;

interface VoiceRecorderProps {
  onComplete: (sample: Blob) => Promise<void>;
  loading?: boolean;
}

export function VoiceRecorder({ onComplete, loading }: VoiceRecorderProps) {
  const [phase, setPhase] = useState<"idle" | "recording" | "uploading" | "done" | "error">("idle");
  const [remaining, setRemaining] = useState(RECORD_SECONDS);
  const [error, setError] = useState<string | null>(null);
  const name = useBabyName() ?? "";
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
    <div>
      <h2 className="font-display text-xl text-ink [font-variation-settings:'SOFT'_100]">Your voice</h2>
      <p className="mt-3 text-sm leading-relaxed text-ink-dim">
        Read anything aloud for {RECORD_SECONDS} seconds in a calm, natural tone. Cribby uses it to settle{" "}
        {babyObject(name)} in your voice before you have to get out of bed.
      </p>

      {phase === "recording" && (
        <div role="status" className="mt-4 flex items-center gap-2.5 text-sm text-ink">
          <span className="breathe h-2.5 w-2.5 rounded-full bg-rose-300" aria-hidden />
          Recording… {remaining}s
        </div>
      )}

      {(phase === "uploading" || loading) && (
        <div role="status" className="mt-4 flex items-center gap-2.5 text-sm text-ink-dim">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-tone border-t-transparent" aria-hidden />
          Creating your voice…
        </div>
      )}

      {error && <p role="alert" className="mt-3 text-sm text-rose-300">{error}</p>}

      <button
        type="button"
        onClick={start}
        disabled={phase === "recording" || phase === "uploading" || loading}
        className="mt-5 w-full rounded-full bg-ink px-4 py-2.5 text-sm font-medium text-[#0a0b15] transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {phase === "done" ? "Record again" : `Record a ${RECORD_SECONDS}-second sample`}
      </button>
      <p className="mt-4 text-xs text-ink-faint">Voice by ElevenLabs</p>
    </div>
  );
}
