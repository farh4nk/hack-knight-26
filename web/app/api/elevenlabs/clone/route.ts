import { NextResponse } from "next/server";

const EL = "https://api.elevenlabs.io";

export async function POST(req: Request) {
  const apiKey = process.env.ELEVENLABS_API_KEY;

  const url = new URL(req.url);
  const name = url.searchParams.get("name") || "CradleEcho Parent";

  const audioBlob = await req.blob();
  if (!audioBlob || audioBlob.size === 0) {
    return NextResponse.json({ error: "Missing audio sample" }, { status: 400 });
  }

  // If no API key configured, provide mock voice_id for local testing
  if (!apiKey || apiKey === "your_elevenlabs_api_key_here") {
    console.warn("[ElevenLabs API] No ELEVENLABS_API_KEY provided. Using mock voice_id.");
    return NextResponse.json({ voice_id: "mock_parent_voice_maya" });
  }

  const formData = new FormData();
  formData.append("name", name);
  formData.append("files", audioBlob, "parent-sample.webm");
  formData.append("remove_background_noise", "true");

  try {
    const res = await fetch(`${EL}/v1/voices/add`, {
      method: "POST",
      headers: { "xi-api-key": apiKey },
      body: formData,
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      return NextResponse.json(
        { error: "ElevenLabs voice clone failed", detail: body },
        { status: res.status }
      );
    }
    return NextResponse.json({ voice_id: body.voice_id });
  } catch (error) {
    return NextResponse.json({ error: String(error) }, { status: 502 });
  }
}
