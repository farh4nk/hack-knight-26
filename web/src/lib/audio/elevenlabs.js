import { SOOTHING_PHRASES } from "./constants.js";

const VOICE_KEY = "cradleecho.voiceId";

export function loadVoiceId() {
  try {
    return localStorage.getItem(VOICE_KEY);
  } catch {
    return null;
  }
}

export function saveVoiceId(id) {
  try {
    if (id) localStorage.setItem(VOICE_KEY, id);
    else localStorage.removeItem(VOICE_KEY);
  } catch {
    /* storage unavailable */
  }
}

/** Task 3.1 — register the recorded sample as an Instant Voice Clone. */
export async function cloneVoice(sample, name = "CradleEcho Parent") {
  const res = await fetch(`/api/elevenlabs/clone?name=${encodeURIComponent(name)}`, {
    method: "POST",
    headers: { "Content-Type": sample.type || "audio/webm" },
    body: sample,
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok || !body.voice_id) throw new Error(body.error ?? "Voice clone failed");
  return body.voice_id;
}

/** Render one phrase in the cloned voice and return it as an object URL. */
export async function synthesize(voiceId, text) {
  const res = await fetch("/api/elevenlabs/tts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ voiceId, text }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error ?? "Text-to-speech failed");
  }
  return URL.createObjectURL(await res.blob());
}

/** Task 3.2 — pre-render the three soothing variations. */
export function renderSoothingSnippets(voiceId) {
  return Promise.all(
    SOOTHING_PHRASES.map(async (text) => ({ text, url: await synthesize(voiceId, text) })),
  );
}
