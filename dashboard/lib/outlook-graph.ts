import { getSession } from "./auth";
import { getValidAccessToken } from "./outlook-oauth";
import { env } from "./env";

export async function resolveGraphToken(): Promise<{ token: string; scope: "user" | "app"; userPath: string } | null> {
  const session = await getSession();
  if (session) {
    const creds = await getValidAccessToken(session.accountId);
    if (creds) {
      return { token: creds.token, scope: "user", userPath: "/me" };
    }
  }

  if (env.outlook.configured) {
    const { getAppToken } = await import("./outlook");
    const token = await getAppToken();
    return { token, scope: "app", userPath: `/users/${encodeURIComponent(env.outlook.mailbox)}` };
  }

  return null;
}

export async function graphFetchAuto(path: string, init: RequestInit = {}): Promise<Response> {
  const resolved = await resolveGraphToken();
  if (!resolved) throw new Error("Outlook not connected");

  const fullPath = path.startsWith("/me") || path.startsWith("/users")
    ? path
    : `${resolved.userPath}${path}`;

  return fetch(`https://graph.microsoft.com/v1.0${fullPath}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${resolved.token}`,
      Accept: "application/json",
      ...(init.headers ?? {}),
    },
    cache: "no-store",
  });
}

export async function graphJsonAuto<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await graphFetchAuto(path, init);
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`Graph ${path} ${res.status}: ${detail.slice(0, 200)}`);
  }
  return res.json() as Promise<T>;
}
