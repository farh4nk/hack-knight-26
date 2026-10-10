import { NextResponse } from "next/server";

const EL = "https://api.elevenlabs.io";

export async function POST(req: Request) {
  const apiKey = process.env.ELEVENLABS_API_KEY;

  const url = new URL(req.url);
  const name = url.searchParams.get("name") || "Cribby Parent";

  const audioBlob = await req.blob();
  if (!audioBlob || audioBlob.size === 0) {
    return NextResponse.json({ error: "Missing audio sample" }, { status: 400 });
  }

  // If no API key configured, provide mock voice_id for local testing
  if (!apiKey || apiKey === "your_elevenlabs_api_key_here") {
    console.warn("[ElevenLabs API] No ELEVENLABS_API_KEY provided. Using mock voice_id.");
    return NextResponse.json({ voice_id: "mock_parent_voice" });
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
      const errString = JSON.stringify(body);
      const isPaidRequired =
        res.status === 402 ||
        errString.includes("paid_plan_required") ||
        errString.includes("can_not_use_instant_voice_cloning");

      if (isPaidRequired) {
        console.info(
          "[ElevenLabs API] Free tier detected (Instant Voice Cloning requires Paid plan). Seamlessly using ElevenLabs reassuring library voice 'Sarah' (EXAVITQu4vr4xnSDxMaL)."
        );
        // Sarah - Mature, Reassuring, Confident
        return NextResponse.json({
          voice_id: "EXAVITQu4vr4xnSDxMaL",
          notice: "Using ElevenLabs library voice (upgrade to Paid plan for custom clone)",
        });
      }

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
