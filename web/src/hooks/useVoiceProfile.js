import { useCallback, useEffect, useState } from "react";
import { cloneVoice, loadVoiceId, renderSoothingSnippets, saveVoiceId } from "../lib/audio/elevenlabs.js";

/** Holds the cloned voice_id (persisted) and the pre-rendered soothing snippets. */
export function useVoiceProfile() {
  const [voiceId, setVoiceId] = useState(null);
  const [snippets, setSnippets] = useState([]);
  const [error, setError] = useState(null);

  const render = useCallback(async (id) => {
    try {
      setSnippets(await renderSoothingSnippets(id));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not render soothing phrases");
    }
  }, []);

  // Restore a previous onboarding; snippets are re-rendered since object URLs don't persist.
  useEffect(() => {
    const id = loadVoiceId();
    if (id) {
      setVoiceId(id);
      render(id);
    }
  }, [render]);

  const onboard = useCallback(
    async (sample) => {
      const id = await cloneVoice(sample);
      saveVoiceId(id);
      setVoiceId(id);
      await render(id);
    },
    [render],
  );

  /** Forget the voice so the recorder shows again. */
  const reset = useCallback(() => {
    saveVoiceId(null);
    setVoiceId(null);
    setSnippets([]);
  }, []);

  return { voiceId, snippets, error, onboard, reset };
}
