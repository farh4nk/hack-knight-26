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
import { useAuth } from "@/context/AuthProvider";

/** Holds the cloned voice_id (persisted in localStorage and Tiger Data) and pre-rendered soothing snippets. */
export function useVoiceProfile() {
  const { baby, updateBaby } = useAuth();
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
    const id = loadVoiceId() || baby?.voice_id || null;
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
  }, [render, babyName, baby?.voice_id]);

  const onboard = useCallback(
    async (sample: Blob) => {
      setLoading(true);
      setError(null);
      try {
        const id = await cloneVoice(sample);
        saveVoiceId(id);
        setVoiceId(id);
        if (baby) {
          void updateBaby({ voice_id: id });
        }
        await render(id, babyName ?? "");
      } catch (e) {
        setError(e instanceof Error ? e.message : "Voice onboarding failed");
      } finally {
        setLoading(false);
      }
    },
    [render, babyName, baby, updateBaby]
  );

  const reset = useCallback(() => {
    saveVoiceId(null);
    setVoiceId(null);
    if (baby) {
      void updateBaby({ voice_id: null });
    }
    setSnippets([]);
    setError(null);
  }, [baby, updateBaby]);

  return { voiceId, snippets, loading, error, onboard, reset };
}
