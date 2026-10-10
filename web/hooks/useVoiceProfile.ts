"use client";

import { useCallback, useEffect, useState } from "react";
import {
  cloneVoice,
  loadVoiceId,
  renderSoothingSnippets,
  saveVoiceId,
  SoothingSnippet,
} from "@/lib/audio/elevenlabs";
import { useBabyName } from "@/lib/babyName";

/** Holds the cloned voice_id (persisted in localStorage) and pre-rendered soothing snippets. */
export function useVoiceProfile() {
  const [voiceId, setVoiceId] = useState<string | null>(null);
  const [snippets, setSnippets] = useState<SoothingSnippet[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // null until the saved name is known; rendering waits for it so each load costs one set of
  // ElevenLabs calls, and re-renders only when the name actually changes.
  const babyName = useBabyName();

  const render = useCallback(async (id: string, name: string) => {
    setLoading(true);
    try {
      const rendered = await renderSoothingSnippets(id, name);
      setSnippets(rendered);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not render soothing phrases");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (babyName === null) return;
    const id = loadVoiceId();
    if (!id) return;
    let cancelled = false;
    Promise.resolve().then(() => {
      if (!cancelled) {
        setVoiceId(id);
        void render(id, babyName);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [render, babyName]);

  const onboard = useCallback(
    async (sample: Blob) => {
      setLoading(true);
      setError(null);
      try {
        const id = await cloneVoice(sample);
        saveVoiceId(id);
        setVoiceId(id);
        await render(id, babyName ?? "");
      } catch (e) {
        setError(e instanceof Error ? e.message : "Voice onboarding failed");
      } finally {
        setLoading(false);
      }
    },
    [render, babyName]
  );

  const reset = useCallback(() => {
    saveVoiceId(null);
    setVoiceId(null);
    setSnippets([]);
    setError(null);
  }, []);

  return { voiceId, snippets, loading, error, onboard, reset };
}
