import { NextResponse } from "next/server";

const EL = "https://api.elevenlabs.io";

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

  // Graceful fallback for mock testing without API key
  if (!apiKey || apiKey === "your_elevenlabs_api_key_here" || voiceId.startsWith("mock_")) {
    console.warn("[ElevenLabs API] Generating fallback audio for text:", text);
    // Return empty / silent mp3 or placeholder audio buffer
    const silentMp3Header = Buffer.from([
      0xff, 0xfb, 0x90, 0x44, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    ]);
    return new Response(silentMp3Header, {
      headers: { "Content-Type": "audio/mpeg" },
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
