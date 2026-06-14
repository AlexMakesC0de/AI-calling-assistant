import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { buildGoogleAuthUrl } from "@/lib/gmail-oauth";
import { env } from "@/lib/env";

export async function GET() {
  const session = await getSession();
  if (!session) {
    return NextResponse.redirect(new URL("/login", process.env.NEXT_PUBLIC_BASE_URL ?? "http://localhost:3000"));
  }

  if (!env.google.configured) {
    return NextResponse.json({ error: "Google OAuth not configured" }, { status: 500 });
  }

  const state = Buffer.from(JSON.stringify({ accountId: session.accountId })).toString("base64url");
  const url = buildGoogleAuthUrl(state);
  return NextResponse.redirect(url);
}
