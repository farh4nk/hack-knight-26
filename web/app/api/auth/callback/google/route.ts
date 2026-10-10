import { NextResponse } from "next/server";
import { SESSION_COOKIE_NAME, createSessionToken, getBackendUrl } from "@/lib/auth";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const code = searchParams.get("code");
  const error = searchParams.get("error");

  const origin =
    process.env.NEXT_PUBLIC_APP_URL ||
    new URL(request.url).origin ||
    "http://localhost:3000";

  if (error || !code) {
    const errorMsg = error || "missing_code";
    return NextResponse.redirect(`${origin}/?auth_error=${encodeURIComponent(errorMsg)}`);
  }

  const clientId = process.env.GOOGLE_CLIENT_ID;
  const clientSecret = process.env.GOOGLE_CLIENT_SECRET;

  if (!clientId || !clientSecret) {
    return NextResponse.redirect(`${origin}/?auth_error=oauth_config_missing`);
  }

  const redirectUri = `${origin.replace(/\/$/, "")}/api/auth/callback/google`;

  try {
    // 1. Exchange code for access token
    const tokenResponse = await fetch("https://oauth2.googleapis.com/token", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        code,
        client_id: clientId,
        client_secret: clientSecret,
        redirect_uri: redirectUri,
        grant_type: "authorization_code",
      }),
    });

    if (!tokenResponse.ok) {
      const errBody = await tokenResponse.text();
      console.error("[Auth Callback] Google token exchange failed:", errBody);
      return NextResponse.redirect(`${origin}/?auth_error=token_exchange_failed`);
    }

    const tokenData = await tokenResponse.json();
    const accessToken = tokenData.access_token;

    // 2. Fetch user profile from Google UserInfo endpoint
    const userinfoResponse = await fetch("https://www.googleapis.com/oauth2/v3/userinfo", {
      headers: { Authorization: `Bearer ${accessToken}` },
    });

    if (!userinfoResponse.ok) {
      console.error("[Auth Callback] Google userinfo fetch failed:", await userinfoResponse.text());
      return NextResponse.redirect(`${origin}/?auth_error=userinfo_fetch_failed`);
    }

    const googleUser = await userinfoResponse.json();

    // 3. Sync with Tiger Data backend API
    const backendUrl = getBackendUrl();
    const syncResponse = await fetch(`${backendUrl}/api/users/sync`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id: googleUser.sub,
        email: googleUser.email,
        name: googleUser.name || "Parent",
        avatar_url: googleUser.picture || null,
      }),
    });

    if (!syncResponse.ok) {
      console.error("[Auth Callback] Tiger Data sync failed:", await syncResponse.text());
      return NextResponse.redirect(`${origin}/?auth_error=database_sync_failed`);
    }

    const syncData = await syncResponse.json();
    const user = syncData.user;
    const baby = syncData.baby;

    // 4. Create signed session token
    const sessionToken = await createSessionToken({ user, baby });

    // 5. Build response with HTTP-only cookie and redirect home
    const response = NextResponse.redirect(`${origin}/?auth_success=1`);
    response.cookies.set({
      name: SESSION_COOKIE_NAME,
      value: sessionToken,
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      path: "/",
      sameSite: "lax",
      maxAge: 60 * 60 * 24 * 7, // 7 days
    });

    return response;
  } catch (err) {
    console.error("[Auth Callback] Unexpected error:", err);
    return NextResponse.redirect(`${origin}/?auth_error=internal_error`);
  }
}
