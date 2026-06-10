import { env } from "./env";

// Microsoft Graph types — only the fields the dashboard surfaces.
export type OutlookAddress = { name?: string; address?: string };

export type OutlookMessageSummary = {
  id: string;
  subject: string;
  bodyPreview: string;
  from?: { emailAddress: OutlookAddress };
  toRecipients?: Array<{ emailAddress: OutlookAddress }>;
  receivedDateTime: string;
  isRead: boolean;
  hasAttachments: boolean;
  importance?: string;
  webLink?: string;
};

export type OutlookMessage = OutlookMessageSummary & {
  ccRecipients?: Array<{ emailAddress: OutlookAddress }>;
  bccRecipients?: Array<{ emailAddress: OutlookAddress }>;
  replyTo?: Array<{ emailAddress: OutlookAddress }>;
  body: { contentType: "html" | "text"; content: string };
  internetMessageId?: string;
};

export type OutlookAttachmentMeta = {
  id: string;
  name: string;
  contentType: string;
  size: number;
  isInline: boolean;
};

export class OutlookNotConfiguredError extends Error {
  constructor() {
    super("Outlook is not configured. Set OUTLOOK_TENANT_ID, OUTLOOK_CLIENT_ID, OUTLOOK_CLIENT_SECRET, and OUTLOOK_MAILBOX.");
    this.name = "OutlookNotConfiguredError";
  }
}

export function outlookConfigured(): boolean {
  return env.outlook.configured;
}

// Token caching — Microsoft tokens last ~3600s. We refresh ~60s before expiry.
let cached: { token: string; expiresAt: number } | null = null;

async function getOutlookToken(): Promise<string> {
  if (!env.outlook.configured) throw new OutlookNotConfiguredError();
  if (cached && cached.expiresAt > Date.now() + 60_000) return cached.token;

  const response = await fetch(
    `https://login.microsoftonline.com/${encodeURIComponent(env.outlook.tenantId)}/oauth2/v2.0/token`,
    {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        client_id: env.outlook.clientId,
        client_secret: env.outlook.clientSecret,
        grant_type: "client_credentials",
        scope: "https://graph.microsoft.com/.default",
      }),
      cache: "no-store",
    }
  );

  if (!response.ok) {
    const text = await response.text().catch(() => "");
    cached = null;
    throw new Error(`Outlook token request failed: ${response.status} ${text.slice(0, 200)}`);
  }

  const json = (await response.json()) as { access_token: string; expires_in: number };
  cached = {
    token: json.access_token,
    expiresAt: Date.now() + json.expires_in * 1000,
  };
  return cached.token;
}

async function graphFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const token = await getOutlookToken();
  return fetch(`https://graph.microsoft.com/v1.0${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/json",
      ...(init.headers ?? {}),
    },
    cache: "no-store",
  });
}

async function graphJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await graphFetch(path, init);
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new Error(`Graph ${path} ${response.status}: ${detail.slice(0, 200)}`);
  }
  return (await response.json()) as T;
}

function userScope(): string {
  return `/users/${encodeURIComponent(env.outlook.mailbox)}`;
}

function folderSegment(): string {
  // The well-known folder name "Inbox" works without lookup; for custom
  // folders, the user supplies a folder ID (or we'd need to resolve by name).
  return `/mailFolders/${encodeURIComponent(env.outlook.folder || "Inbox")}`;
}

export type OutlookListOptions = { top?: number; search?: string };

export type OutlookListResponse = {
  value: OutlookMessageSummary[];
  total?: number;
  configured: true;
};

export async function listOutlookMessages(opts: OutlookListOptions = {}): Promise<OutlookListResponse> {
  const top = Math.min(Math.max(opts.top ?? 50, 1), 100);
  // $select keeps responses small; $orderby for consistent paging.
  const select = [
    "id",
    "subject",
    "bodyPreview",
    "from",
    "toRecipients",
    "receivedDateTime",
    "isRead",
    "hasAttachments",
    "importance",
    "webLink",
  ].join(",");

  const params = new URLSearchParams({
    $top: String(top),
    $select: select,
  });

  let path: string;
  if (opts.search?.trim()) {
    // Graph $search uses Microsoft's KQL syntax, e.g. `from:foo subject:"hello"`.
    // It can't be combined with $orderby, so we let Graph rank by relevance.
    params.set("$search", `"${opts.search.trim().replace(/"/g, '\\"')}"`);
    path = `${userScope()}${folderSegment()}/messages?${params}`;
  } else {
    params.set("$orderby", "receivedDateTime desc");
    path = `${userScope()}${folderSegment()}/messages?${params}`;
  }

  const json = await graphJson<{ value: OutlookMessageSummary[]; "@odata.count"?: number }>(path, {
    headers: opts.search ? { ConsistencyLevel: "eventual" } : undefined,
  });
  return { value: json.value, total: json["@odata.count"], configured: true };
}

export async function getOutlookMessage(id: string): Promise<OutlookMessage> {
  return graphJson<OutlookMessage>(`${userScope()}/messages/${encodeURIComponent(id)}`);
}

export async function listOutlookAttachments(messageId: string): Promise<OutlookAttachmentMeta[]> {
  const json = await graphJson<{ value: Array<OutlookAttachmentMeta & { "@odata.type"?: string }> }>(
    `${userScope()}/messages/${encodeURIComponent(messageId)}/attachments?$select=id,name,contentType,size,isInline`
  );
  return json.value;
}

export async function fetchOutlookAttachmentValue(messageId: string, attachmentId: string): Promise<Response> {
  return graphFetch(
    `${userScope()}/messages/${encodeURIComponent(messageId)}/attachments/${encodeURIComponent(attachmentId)}/$value`
  );
}

export async function setOutlookRead(messageId: string, isRead: boolean): Promise<void> {
  const response = await graphFetch(`${userScope()}/messages/${encodeURIComponent(messageId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ isRead }),
  });
  if (!response.ok) {
    throw new Error(`Outlook PATCH /messages/${messageId} failed: ${response.status}`);
  }
}

export function flattenAddresses(list: Array<{ emailAddress: OutlookAddress }> | undefined): string {
  if (!list || list.length === 0) return "";
  return list
    .map((r) => r.emailAddress?.address ?? "")
    .filter(Boolean)
    .join(", ");
}
