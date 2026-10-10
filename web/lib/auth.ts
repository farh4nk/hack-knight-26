import { SignJWT, jwtVerify } from "jose";

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  avatar_url: string | null;
}

export interface BabyProfile {
  id: number;
  parent_id: string;
  name: string;
  bedtime: string;
  wake_time: string;
  voice_id?: string | null;
}

export interface SessionData {
  user: AuthUser;
  baby: BabyProfile;
}

export const SESSION_COOKIE_NAME = "cradleecho_session";

function getSecretKey(): Uint8Array {
  const secret = process.env.AUTH_SECRET || "cradleecho_dev_secret_key_needs_32_bytes_min_2026";
  return new TextEncoder().encode(secret);
}

export function getBackendUrl(): string {
  return (
    process.env.BACKEND_API_URL ||
    process.env.NEXT_PUBLIC_ANALYTICS_URL ||
    "http://localhost:8001"
  ).replace(/\/$/, "");
}

export async function createSessionToken(session: SessionData): Promise<string> {
  const secretKey = getSecretKey();
  return await new SignJWT({
    user: session.user,
    baby: session.baby,
  })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime("7d")
    .sign(secretKey);
}

export async function verifySessionToken(token: string): Promise<SessionData | null> {
  try {
    const secretKey = getSecretKey();
    const { payload } = await jwtVerify(token, secretKey);
    if (!payload.user || !payload.baby) return null;
    return {
      user: payload.user as AuthUser,
      baby: payload.baby as BabyProfile,
    };
  } catch {
    return null;
  }
}
