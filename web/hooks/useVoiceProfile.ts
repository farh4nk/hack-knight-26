"use client";

import { useCallback, useEffect, useState } from "react";
import {
  cloneVoice,
  loadVoiceId,
  renderSoothingSnippets,
  saveVoiceId,
  SoothingSnippet,
} from "@/lib/audio/elevenlabs";

/** Holds the cloned voice_id (persisted in localStorage) and pre-rendered soothing snippets. */
export function useVoiceProfile() {
  const [voiceId, setVoiceId] = useState<string | null>(null);
  const [snippets, setSnippets] = useState<SoothingSnippet[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const render = useCallback(async (id: string) => {
    setLoading(true);
    try {
      const rendered = await renderSoothingSnippets(id);
      setSnippets(rendered);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not render soothing phrases");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const id = loadVoiceId();
    if (id) {
      setVoiceId(id);
      render(id);
    }
  }, [render]);

  const onboard = useCallback(
    async (sample: Blob) => {
      setLoading(true);
      setError(null);
      try {
        const id = await cloneVoice(sample);
        saveVoiceId(id);
        setVoiceId(id);
        await render(id);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Voice onboarding failed");
      } finally {
        setLoading(false);
      }
    },
    [render]
  );

  const reset = useCallback(() => {
    saveVoiceId(null);
    setVoiceId(null);
    setSnippets([]);
    setError(null);
  }, []);

  return { voiceId, snippets, loading, error, onboard, reset };
}
