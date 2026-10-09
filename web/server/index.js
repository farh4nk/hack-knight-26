// Tiny proxy so the ElevenLabs API key never reaches the browser.
import "dotenv/config";
import dotenv from "dotenv";
import express from "express";

dotenv.config({ path: ".env.local" });

const app = express();
const PORT = process.env.API_PORT || 8787;
const EL = "https://api.elevenlabs.io";

function key(res) {
  const k = process.env.ELEVENLABS_API_KEY;
  if (!k) res.status(500).json({ error: "ELEVENLABS_API_KEY is not set" });
  return k;
}

// Task 3.1 — Instant Voice Clone. Body is the raw recorded audio.
app.post("/api/elevenlabs/clone", express.raw({ type: "*/*", limit: "25mb" }), async (req, res) => {
  const apiKey = key(res);
  if (!apiKey) return;
  if (!Buffer.isBuffer(req.body) || req.body.length === 0) {
    return res.status(400).json({ error: "Missing audio sample" });
  }

  const form = new FormData();
  form.append("name", String(req.query.name || "CradleEcho Parent"));
  form.append(
    "files",
    new Blob([req.body], { type: req.headers["content-type"] || "audio/webm" }),
    "parent-sample.webm",
  );
  form.append("remove_background_noise", "true");

  try {
    const r = await fetch(`${EL}/v1/voices/add`, {
      method: "POST",
      headers: { "xi-api-key": apiKey },
      body: form,
    });
    const body = await r.json().catch(() => ({}));
    if (!r.ok) return res.status(r.status).json({ error: "ElevenLabs voice clone failed", detail: body });
    res.json({ voice_id: body.voice_id });
  } catch (e) {
    res.status(502).json({ error: String(e) });
  }
});

// Task 3.2 — text-to-speech in the cloned voice (also used for "Talk to baby").
app.post("/api/elevenlabs/tts", express.json(), async (req, res) => {
  const apiKey = key(res);
  if (!apiKey) return;
  const { voiceId, text } = req.body || {};
  if (!voiceId || !text) return res.status(400).json({ error: "voiceId and text are required" });

  try {
    const r = await fetch(`${EL}/v1/text-to-speech/${encodeURIComponent(voiceId)}`, {
      method: "POST",
      headers: { "xi-api-key": apiKey, "Content-Type": "application/json", Accept: "audio/mpeg" },
      body: JSON.stringify({
        text,
        model_id: "eleven_multilingual_v2",
        voice_settings: { stability: 0.75, similarity_boost: 0.8, style: 0.1 },
      }),
    });
    if (!r.ok) {
      return res.status(r.status).json({ error: "ElevenLabs TTS failed", detail: await r.text() });
    }
    res.type("audio/mpeg").send(Buffer.from(await r.arrayBuffer()));
  } catch (e) {
    res.status(502).json({ error: String(e) });
  }
});

app.listen(PORT, () => console.log(`API proxy on http://localhost:${PORT}`));
