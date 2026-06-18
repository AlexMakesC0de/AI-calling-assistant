import { NextResponse, type NextRequest } from "next/server";
import { getSession } from "@/lib/auth";
import { exchangeCode, fetchUserEmail, saveTokens } from "@/lib/outlook-oauth";

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
    const desc = searchParams.get("error_description") ?? error;
    return NextResponse.redirect(
      new URL(`/inbox/outlook?error=${encodeURIComponent(desc)}`, baseUrl),
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

  const codeVerifier = request.cookies.get("pkce_verifier")?.value;

  try {
    const tokens = await exchangeCode(code, codeVerifier);
    const mailboxEmail = await fetchUserEmail(tokens.access_token);
    await saveTokens(session.accountId, tokens, mailboxEmail);
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Token exchange failed";
    return NextResponse.redirect(
      new URL(`/inbox/outlook?error=${encodeURIComponent(msg)}`, baseUrl),
    );
  }

  const response = NextResponse.redirect(new URL("/inbox/outlook", baseUrl));
  response.cookies.delete("pkce_verifier");
  return response;
}
