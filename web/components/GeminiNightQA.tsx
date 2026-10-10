"use client";

import { useState } from "react";
import { analyticsUrl, BABY_NAME } from "@/lib/config";

const SUGGESTED_QUESTIONS = [
  `How was ${BABY_NAME} resting around 3 AM?`,
  `How steady was ${BABY_NAME}’s breathing overnight?`,
  `Did the auto-soothe voice settle her quickly?`,
  `How does her sleep compare to normal infant baselines?`,
];

interface GeminiNightQAProps {
  bedtime?: string;
  wakeTime?: string;
}

export function GeminiNightQA({ bedtime = "20:00", wakeTime = "07:00" }: GeminiNightQAProps) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<string | null>(null);
  const [modelUsed, setModelUsed] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAsk = async (qText?: string) => {
    const q = (qText || question).trim();
    if (!q || loading) return;

    setLoading(true);
    setError(null);
    setAnswer(null);

    try {
      const res = await fetch(`${analyticsUrl()}/api/nightly-qa`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: q,
          baby_name: BABY_NAME,
          bedtime,
          wake_time: wakeTime,
        }),
      });

      if (!res.ok) throw new Error("Could not reach Gemini sleep assistant");
      const data = await res.json();
      setAnswer(data.answer);
      setModelUsed(data.model_used);
    } catch {
      setError("Gemini assistant unavailable. Make sure analytics is running on :8001.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="mt-12 rounded-3xl bg-white/5 p-6 ring-1 ring-white/10 sm:p-8">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <svg className="h-5 w-5 text-tone" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M13 10V3L4 14h7v7l9-11h-7z"
            />
          </svg>
          <h2 className="font-display text-2xl text-ink [font-variation-settings:'SOFT'_100]">
            Ask Gemini About {BABY_NAME}’s Night
          </h2>
        </div>
        <span className="text-xs text-ink-faint">Interactive Sleep Intelligence</span>
      </div>

      <p className="mt-2 text-sm text-ink-dim">
        Ask anything about {BABY_NAME}’s vital signs, restlessness episodes, or sleep depth. Gemini analyzes the full night’s Timescale telemetry to answer.
      </p>

      {/* Suggested question chips */}
      <div className="mt-5 flex flex-wrap gap-2">
        {SUGGESTED_QUESTIONS.map((sq, idx) => (
          <button
            key={idx}
            type="button"
            onClick={() => {
              setQuestion(sq);
              handleAsk(sq);
            }}
            disabled={loading}
            className="rounded-full bg-white/5 px-3 py-1.5 text-xs text-ink-dim ring-1 ring-white/10 transition hover:bg-white/10 hover:text-ink disabled:opacity-50"
          >
            {sq}
          </button>
        ))}
      </div>

      {/* Question input form */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleAsk();
        }}
        className="mt-4 flex gap-2"
      >
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={`e.g. Was Maya breathing calmly during her 2 AM sleep cycle?`}
          className="min-w-0 flex-1 rounded-2xl bg-white/5 px-4 py-3 text-sm text-ink placeholder:text-ink-faint ring-1 ring-white/10 focus:outline-none focus:ring-tone/50"
        />
        <button
          type="submit"
          disabled={!question.trim() || loading}
          className="rounded-2xl bg-ink px-5 py-3 text-sm font-medium text-[#0a0b15] transition hover:opacity-90 disabled:opacity-40"
        >
          {loading ? "Thinking…" : "Ask"}
        </button>
      </form>

      {/* Loading state */}
      {loading && (
        <div role="status" className="mt-6 flex items-center gap-3 text-sm text-ink-dim">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-tone border-t-transparent" />
          Analyzing Tiger Data vitals with Gemini…
        </div>
      )}

      {/* Error state */}
      {error && !loading && (
        <p className="mt-4 text-sm text-rose-300">{error}</p>
      )}

      {/* Answer card */}
      {answer && !loading && (
        <div className="mt-6 rounded-2xl bg-tone/10 p-5 ring-1 ring-tone/25">
          <div className="flex items-center justify-between text-xs text-tone">
            <span className="font-semibold uppercase tracking-wider">Gemini Wellness Synthesis</span>
            {modelUsed && <span className="text-ink-faint">Model: {modelUsed}</span>}
          </div>
          <p className="mt-2.5 font-display text-base leading-relaxed text-ink [font-variation-settings:'SOFT'_100] sm:text-lg">
            {answer}
          </p>
        </div>
      )}
    </section>
  );
}
