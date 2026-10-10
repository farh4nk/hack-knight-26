import { NextResponse } from "next/server";
import { SESSION_COOKIE_NAME } from "@/lib/auth";

export async function POST() {
  const response = NextResponse.json({ success: true, message: "Logged out" });
  response.cookies.delete(SESSION_COOKIE_NAME);
  return response;
}

export async function GET(request: Request) {
  const origin =
    process.env.NEXT_PUBLIC_APP_URL ||
    new URL(request.url).origin ||
    "http://localhost:3000";

  const response = NextResponse.redirect(`${origin}/`);
  response.cookies.delete(SESSION_COOKIE_NAME);
  return response;
}
