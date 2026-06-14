import { env } from "./env";
import { prisma } from "./prisma";
import { encrypt, decrypt } from "./crypto";

const SCOPES = "openid email profile https://www.googleapis.com/auth/gmail.readonly";

function redirectUri(): string {
  return process.env.GOOGLE_REDIRECT_URI ?? "http://localhost:3000/api/gmail/callback";
}

export function buildGoogleAuthUrl(state: string): string {
  const params = new URLSearchParams({
    client_id: env.google.clientId,
    redirect_uri: redirectUri(),
    response_type: "code",
    scope: SCOPES,
    access_type: "offline",
    prompt: "consent",
    state,
  });
  return `https://accounts.google.com/o/oauth2/v2/auth?${params}`;
}

type TokenResponse = {
  access_token: string;
  refresh_token?: string;
  expires_in: number;
  token_type: string;
};

export async function exchangeGoogleCode(code: string): Promise<TokenResponse> {
  const res = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      client_id: env.google.clientId,
      client_secret: env.google.clientSecret,
      grant_type: "authorization_code",
      code,
      redirect_uri: redirectUri(),
    }),
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Google token error ${res.status}: ${text.slice(0, 300)}`);
  }
  return res.json() as Promise<TokenResponse>;
}

async function refreshGoogleToken(refreshToken: string): Promise<TokenResponse> {
  const res = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      client_id: env.google.clientId,
      client_secret: env.google.clientSecret,
      grant_type: "refresh_token",
      refresh_token: refreshToken,
    }),
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Google refresh error ${res.status}: ${text.slice(0, 300)}`);
  }
  return res.json() as Promise<TokenResponse>;
}

export async function fetchGoogleEmail(accessToken: string): Promise<string> {
  const res = await fetch("https://www.googleapis.com/oauth2/v2/userinfo", {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Google userinfo failed: ${res.status}`);
  const data = (await res.json()) as { email?: string };
  return data.email ?? "unknown";
}

type StoredToken = {
  access_token: string;
  refresh_token: string;
  expires_at: Date;
  mailbox_email: string;
};

export async function saveGmailTokens(
  accountId: number,
  tokens: TokenResponse,
  mailboxEmail: string,
  existingRefreshToken?: string,
): Promise<void> {
  const expiresAt = new Date(Date.now() + tokens.expires_in * 1000);
  const refreshToken = tokens.refresh_token ?? existingRefreshToken ?? "";
  const encAccessToken = encrypt(tokens.access_token);
  const encRefreshToken = refreshToken ? encrypt(refreshToken) : "";
  await prisma.$executeRaw`
    INSERT INTO gmail_token (account_id, access_token, refresh_token, expires_at, mailbox_email, updated_at)
    VALUES (${accountId}, ${encAccessToken}, ${encRefreshToken}, ${expiresAt}, ${mailboxEmail}, NOW())
    ON CONFLICT (account_id)
    DO UPDATE SET
      access_token  = EXCLUDED.access_token,
      refresh_token = CASE WHEN EXCLUDED.refresh_token = '' THEN gmail_token.refresh_token ELSE EXCLUDED.refresh_token END,
      expires_at    = EXCLUDED.expires_at,
      mailbox_email = EXCLUDED.mailbox_email,
      updated_at    = NOW()
  `;
}

export async function deleteGmailTokens(accountId: number): Promise<void> {
  await prisma.$executeRaw`DELETE FROM gmail_token WHERE account_id = ${accountId}`;
}

export async function getStoredGmailToken(accountId: number): Promise<StoredToken | null> {
  const rows = await prisma.$queryRaw<StoredToken[]>`
    SELECT access_token, refresh_token, expires_at, mailbox_email
    FROM gmail_token WHERE account_id = ${accountId} LIMIT 1
  `;
  if (!rows[0]) return null;
  return {
    ...rows[0],
    access_token: decrypt(rows[0].access_token),
    refresh_token: decrypt(rows[0].refresh_token),
  };
}

export async function getValidGmailToken(accountId: number): Promise<{ token: string; email: string } | null> {
  const stored = await getStoredGmailToken(accountId);
  if (!stored) return null;

  if (stored.expires_at.getTime() > Date.now() + 60_000) {
    return { token: stored.access_token, email: stored.mailbox_email };
  }

  try {
    const refreshed = await refreshGoogleToken(stored.refresh_token);
    await saveGmailTokens(accountId, refreshed, stored.mailbox_email, stored.refresh_token);
    return { token: refreshed.access_token, email: stored.mailbox_email };
  } catch {
    await deleteGmailTokens(accountId);
    return null;
  }
}
