import { randomBytes, createHash } from "crypto";
import { env } from "./env";
import { prisma } from "./prisma";
import { encrypt, decrypt } from "./crypto";

const AUTHORITY = "https://login.microsoftonline.com/common/oauth2/v2.0";
const SCOPES = "openid email profile offline_access Mail.Read User.Read";

function redirectUri(): string {
  return process.env.OUTLOOK_REDIRECT_URI ?? "http://localhost:3000/api/outlook/callback";
}

export function generateCodeVerifier(): string {
  return randomBytes(32).toString("base64url");
}

function deriveCodeChallenge(verifier: string): string {
  return createHash("sha256").update(verifier).digest("base64url");
}

export function buildAuthUrl(state: string, codeChallenge?: string): string {
  const params = new URLSearchParams({
    client_id: env.outlook.clientId,
    response_type: "code",
    redirect_uri: redirectUri(),
    scope: SCOPES,
    response_mode: "query",
    state,
    prompt: "consent",
  });
  if (codeChallenge) {
    params.set("code_challenge", codeChallenge);
    params.set("code_challenge_method", "S256");
  }
  return `${AUTHORITY}/authorize?${params}`;
}

export function buildAuthUrlWithPkce(state: string): { url: string; codeVerifier: string } {
  const codeVerifier = generateCodeVerifier();
  const codeChallenge = deriveCodeChallenge(codeVerifier);
  const url = buildAuthUrl(state, codeChallenge);
  return { url, codeVerifier };
}

type TokenResponse = {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  id_token?: string;
};

async function tokenRequest(body: URLSearchParams): Promise<TokenResponse> {
  const res = await fetch(`${AUTHORITY}/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Microsoft token error ${res.status}: ${text.slice(0, 300)}`);
  }
  return res.json() as Promise<TokenResponse>;
}

export async function exchangeCode(code: string, codeVerifier?: string): Promise<TokenResponse> {
  const params = new URLSearchParams({
    client_id: env.outlook.clientId,
    grant_type: "authorization_code",
    code,
    redirect_uri: redirectUri(),
    scope: SCOPES,
  });
  if (env.outlook.clientSecret) params.set("client_secret", env.outlook.clientSecret);
  if (codeVerifier) params.set("code_verifier", codeVerifier);
  return tokenRequest(params);
}

async function refreshAccessToken(refreshToken: string): Promise<TokenResponse> {
  const params = new URLSearchParams({
    client_id: env.outlook.clientId,
    grant_type: "refresh_token",
    refresh_token: refreshToken,
    scope: SCOPES,
  });
  if (env.outlook.clientSecret) params.set("client_secret", env.outlook.clientSecret);
  return tokenRequest(params);
}

export async function fetchUserEmail(accessToken: string): Promise<string> {
  const res = await fetch("https://graph.microsoft.com/v1.0/me", {
    headers: { Authorization: `Bearer ${accessToken}`, Accept: "application/json" },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Graph /me failed: ${res.status}`);
  const data = (await res.json()) as { mail?: string; userPrincipalName?: string };
  return data.mail || data.userPrincipalName || "unknown";
}

type StoredToken = {
  access_token: string;
  refresh_token: string;
  expires_at: Date;
  mailbox_email: string;
};

export async function saveTokens(
  accountId: number,
  tokens: TokenResponse,
  mailboxEmail: string,
): Promise<void> {
  const expiresAt = new Date(Date.now() + tokens.expires_in * 1000);
  const encAccessToken = encrypt(tokens.access_token);
  const encRefreshToken = encrypt(tokens.refresh_token);
  await prisma.$executeRaw`
    INSERT INTO outlook_token (account_id, access_token, refresh_token, expires_at, mailbox_email, updated_at)
    VALUES (${accountId}, ${encAccessToken}, ${encRefreshToken}, ${expiresAt}, ${mailboxEmail}, NOW())
    ON CONFLICT (account_id)
    DO UPDATE SET
      access_token  = EXCLUDED.access_token,
      refresh_token = EXCLUDED.refresh_token,
      expires_at    = EXCLUDED.expires_at,
      mailbox_email = EXCLUDED.mailbox_email,
      updated_at    = NOW()
  `;
}

export async function deleteTokens(accountId: number): Promise<void> {
  await prisma.$executeRaw`DELETE FROM outlook_token WHERE account_id = ${accountId}`;
}

export async function getStoredToken(accountId: number): Promise<StoredToken | null> {
  const rows = await prisma.$queryRaw<StoredToken[]>`
    SELECT access_token, refresh_token, expires_at, mailbox_email
    FROM outlook_token WHERE account_id = ${accountId} LIMIT 1
  `;
  if (!rows[0]) return null;
  return {
    ...rows[0],
    access_token: decrypt(rows[0].access_token),
    refresh_token: decrypt(rows[0].refresh_token),
  };
}

export async function getValidAccessToken(accountId: number): Promise<{ token: string; email: string } | null> {
  const stored = await getStoredToken(accountId);
  if (!stored) return null;

  if (stored.expires_at.getTime() > Date.now() + 60_000) {
    return { token: stored.access_token, email: stored.mailbox_email };
  }

  try {
    const refreshed = await refreshAccessToken(stored.refresh_token);
    await saveTokens(accountId, refreshed, stored.mailbox_email);
    return { token: refreshed.access_token, email: stored.mailbox_email };
  } catch {
    await deleteTokens(accountId);
    return null;
  }
}

export async function userGraphFetch(accountId: number, path: string, init: RequestInit = {}): Promise<Response> {
  const creds = await getValidAccessToken(accountId);
  if (!creds) throw new Error("Outlook not connected — no valid token for this account.");
  return fetch(`https://graph.microsoft.com/v1.0${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${creds.token}`,
      Accept: "application/json",
      ...(init.headers ?? {}),
    },
    cache: "no-store",
  });
}

export async function userGraphJson<T>(accountId: number, path: string, init?: RequestInit): Promise<T> {
  const res = await userGraphFetch(accountId, path, init);
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`Graph ${path} ${res.status}: ${detail.slice(0, 200)}`);
  }
  return res.json() as Promise<T>;
}
