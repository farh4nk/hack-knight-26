import { NextResponse } from "next/server";

const EL = "https://api.elevenlabs.io";

// Helper to synthesize a gentle calming chime WAV when in mock/testing mode
function generateLullabyChimeWav(): Buffer {
  const sampleRate = 22050;
  const durationSec = 3.5;
  const numSamples = Math.floor(sampleRate * durationSec);
  const buffer = Buffer.alloc(44 + numSamples * 2);

  buffer.write("RIFF", 0);
  buffer.writeUInt32LE(36 + numSamples * 2, 4);
  buffer.write("WAVE", 8);
  buffer.write("fmt ", 12);
  buffer.writeUInt32LE(16, 16);
  buffer.writeUInt16LE(1, 20); // PCM
  buffer.writeUInt16LE(1, 22); // mono
  buffer.writeUInt32LE(sampleRate, 24);
  buffer.writeUInt32LE(sampleRate * 2, 28);
  buffer.writeUInt16LE(2, 32);
  buffer.writeUInt16LE(16, 34);
  buffer.write("data", 36);
  buffer.writeUInt32LE(numSamples * 2, 40);

  // Soothing lullaby sequence: C5 (523Hz), G4 (392Hz), E4 (330Hz), C4 (262Hz)
  const notes = [523.25, 392.0, 329.63, 261.63];
  for (let i = 0; i < numSamples; i++) {
    const t = i / sampleRate;
    const noteIdx = Math.min(Math.floor(t / 0.8), notes.length - 1);
    const noteT = t % 0.8;
    const freq = notes[noteIdx];
    const env = Math.exp(-noteT * 3.2);
    const val = 0.25 * Math.sin(2 * Math.PI * freq * noteT) * env;
    const sample = Math.max(-32768, Math.min(32767, Math.floor(val * 32767)));
    buffer.writeInt16LE(sample, 44 + i * 2);
  }
  return buffer;
}

export async function POST(req: Request) {
  const apiKey = process.env.ELEVENLABS_API_KEY;

  let body: { voiceId?: string; text?: string } = {};
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const { voiceId, text } = body;
  if (!voiceId || !text) {
    return NextResponse.json({ error: "voiceId and text are required" }, { status: 400 });
  }

  // Graceful fallback for demo/testing without API key
  if (!apiKey || apiKey === "your_elevenlabs_api_key_here" || voiceId.startsWith("mock_")) {
    console.info("[TTS Mock Fallback] Playing calming lullaby chime for text:", text);
    const chimeWav = generateLullabyChimeWav();
    return new Response(new Uint8Array(chimeWav), {
      headers: { "Content-Type": "audio/wav" },
    });
  }

  try {
    const res = await fetch(`${EL}/v1/text-to-speech/${encodeURIComponent(voiceId)}`, {
      method: "POST",
      headers: {
        "xi-api-key": apiKey,
        "Content-Type": "application/json",
        Accept: "audio/mpeg",
      },
      body: JSON.stringify({
        text,
        model_id: "eleven_multilingual_v2",
        voice_settings: { stability: 0.75, similarity_boost: 0.8, style: 0.1 },
      }),
    });

    if (!res.ok) {
      const errText = await res.text();
      return NextResponse.json(
        { error: "ElevenLabs TTS failed", detail: errText },
        { status: res.status }
      );
    }

    const audioBuffer = await res.arrayBuffer();
    return new Response(audioBuffer, {
      headers: {
        "Content-Type": "audio/mpeg",
        "Cache-Control": "public, max-age=3600",
      },
    });
  } catch (error) {
    return NextResponse.json({ error: String(error) }, { status: 502 });
  }
}
