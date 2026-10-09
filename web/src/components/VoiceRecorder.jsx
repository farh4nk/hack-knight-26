import { useEffect, useRef, useState } from "react";

const RECORD_SECONDS = 10;

/** 10-second mic recorder. `onComplete(blob)` should resolve once cloning is finished. */
export default function VoiceRecorder({ onComplete }) {
  const [phase, setPhase] = useState("idle"); // idle | recording | uploading | done | error
  const [remaining, setRemaining] = useState(RECORD_SECONDS);
  const [error, setError] = useState(null);
  const recorderRef = useRef(null);
  const tickRef = useRef(null);

  useEffect(
    () => () => {
      clearInterval(tickRef.current);
      recorderRef.current?.stream.getTracks().forEach((t) => t.stop());
    },
    [],
  );

  async function start() {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const chunks = [];
      const rec = new MediaRecorder(stream);
      recorderRef.current = rec;

      rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        clearInterval(tickRef.current);
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
      setError("Microphone access was blocked. Allow it in the browser and try again.");
      setPhase("error");
    }
  }

  return (
    <section className="card">
      <h2>Record your voice</h2>
      <p className="muted">
        Read anything aloud for {RECORD_SECONDS} seconds, in a calm, natural tone. We’ll use it to
        soothe your baby in your voice.
      </p>

      {phase === "recording" && (
        <div role="status" className="rec">● Recording… {remaining}s</div>
      )}
      {phase === "uploading" && <div role="status">Creating your voice…</div>}
      {phase === "done" && <div role="status">Voice ready ✓</div>}
      {error && <p role="alert" className="err">{error}</p>}

      <button type="button" onClick={start} disabled={phase === "recording" || phase === "uploading"}>
        {phase === "done" ? "Re-record" : "Start recording"}
      </button>
    </section>
  );
}
