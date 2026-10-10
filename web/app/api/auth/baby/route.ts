import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { SESSION_COOKIE_NAME, getBackendUrl, verifySessionToken } from "@/lib/auth";

export async function PUT(request: Request) {
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE_NAME)?.value;

  if (!token) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const session = await verifySessionToken(token);
  if (!session) {
    return NextResponse.json({ error: "Invalid session" }, { status: 401 });
  }

  try {
    const body = await request.json();
    const backendUrl = getBackendUrl();
    const res = await fetch(`${backendUrl}/api/babies/${session.baby.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const err = await res.text();
      return NextResponse.json({ error: err }, { status: res.status });
    }

    const updated = await res.json();
    return NextResponse.json(updated);
  } catch (err) {
    console.error("[Baby API] Error updating baby profile:", err);
    return NextResponse.json({ error: "Failed to update baby profile" }, { status: 500 });
  }
}
