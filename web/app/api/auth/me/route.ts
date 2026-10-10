import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { SESSION_COOKIE_NAME, getBackendUrl, verifySessionToken } from "@/lib/auth";

export async function GET() {
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE_NAME)?.value;

  if (!token) {
    return NextResponse.json({
      authenticated: false,
      user: null,
      baby: null,
    });
  }

  const session = await verifySessionToken(token);
  if (!session) {
    return NextResponse.json({
      authenticated: false,
      user: null,
      baby: null,
    });
  }

  // Attempt to fetch fresh baby profile from Tiger Data backend API
  let baby = session.baby;
  try {
    const backendUrl = getBackendUrl();
    const res = await fetch(`${backendUrl}/api/users/${session.user.id}/baby`, {
      cache: "no-store",
    });
    if (res.ok) {
      baby = await res.json();
    }
  } catch {
    // Backend temporarily unreachable, fall back to JWT cached profile
  }

  return NextResponse.json({
    authenticated: true,
    user: session.user,
    baby,
  });
}
