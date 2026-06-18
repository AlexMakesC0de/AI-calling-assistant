import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { buildAuthUrlWithPkce } from "@/lib/outlook-oauth";

export async function GET() {
  const session = await getSession();
  if (!session) {
    return NextResponse.redirect(new URL("/login", process.env.NEXT_PUBLIC_BASE_URL ?? "http://localhost:3000"));
  }

  const state = Buffer.from(JSON.stringify({ accountId: session.accountId })).toString("base64url");
  const { url, codeVerifier } = buildAuthUrlWithPkce(state);

  const response = NextResponse.redirect(url);
  response.cookies.set("pkce_verifier", codeVerifier, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/api/outlook/callback",
    maxAge: 600,
  });
  return response;
}
