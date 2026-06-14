import { NextResponse, type NextRequest } from "next/server";
import { getSession } from "@/lib/auth";
import { exchangeGoogleCode, fetchGoogleEmail, saveGmailTokens } from "@/lib/gmail-oauth";

export async function GET(request: NextRequest) {
  const baseUrl = process.env.NEXT_PUBLIC_BASE_URL ?? "http://localhost:3000";
  const session = await getSession();
  if (!session) {
    return NextResponse.redirect(new URL("/login", baseUrl));
  }

  const { searchParams } = request.nextUrl;
  const code = searchParams.get("code");
  const error = searchParams.get("error");
  const stateParam = searchParams.get("state");

  if (error) {
    return NextResponse.redirect(
      new URL(`/inbox/outlook?error=${encodeURIComponent(error)}`, baseUrl),
    );
  }

  if (!code || !stateParam) {
    return NextResponse.redirect(
      new URL("/inbox/outlook?error=Missing+code+or+state", baseUrl),
    );
  }

  let stateAccountId: number;
  try {
    const parsed = JSON.parse(Buffer.from(stateParam, "base64url").toString()) as { accountId: number };
    stateAccountId = parsed.accountId;
  } catch {
    return NextResponse.redirect(
      new URL("/inbox/outlook?error=Invalid+state", baseUrl),
    );
  }

  if (stateAccountId !== session.accountId) {
    return NextResponse.redirect(
      new URL("/inbox/outlook?error=Session+mismatch", baseUrl),
    );
  }

  try {
    const tokens = await exchangeGoogleCode(code);
    const email = await fetchGoogleEmail(tokens.access_token);
    await saveGmailTokens(session.accountId, tokens, email);
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Token exchange failed";
    return NextResponse.redirect(
      new URL(`/inbox/outlook?error=${encodeURIComponent(msg)}`, baseUrl),
    );
  }

  return NextResponse.redirect(new URL("/inbox/outlook", baseUrl));
}
