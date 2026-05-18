import { env } from "./env";

// Mailpit's HTTP API: https://mailpit.axllent.org/docs/api-v1/
// The dashboard talks to Mailpit through these helpers (server-side) so the
// browser never needs network access to the mailpit container directly.

export type MailpitAddress = { Name: string; Address: string };

export type MailpitMessageSummary = {
  ID: string;
  MessageID: string;
  Read: boolean;
  From: MailpitAddress;
  To: MailpitAddress[];
  Subject: string;
  Created: string;
  Size: number;
  Attachments: number;
  Snippet: string;
  Tags?: string[];
};

export type MailpitListResponse = {
  total: number;
  unread: number;
  count: number;
  messages_count: number;
  start: number;
  tags?: string[];
  messages: MailpitMessageSummary[];
};

export type MailpitAttachment = {
  PartID: string;
  FileName: string;
  ContentType: string;
  ContentID?: string;
  Size: number;
};

export type MailpitMessage = {
  ID: string;
  MessageID: string;
  From: MailpitAddress;
  To: MailpitAddress[];
  Cc?: MailpitAddress[];
  Bcc?: MailpitAddress[];
  ReplyTo?: MailpitAddress[];
  ReturnPath?: string;
  Subject: string;
  Date: string;
  Size: number;
  Text: string;
  HTML: string;
  Tags?: string[];
  Attachments?: MailpitAttachment[];
  Inline?: MailpitAttachment[];
};

export type MailpitInfo = {
  Version: string;
  Database: string;
  DatabaseSize: number;
  Messages: number;
  Unread: number;
  Tags: Record<string, number>;
  RuntimeStats: { Uptime: number };
};

async function mailpitFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${env.mailpitBaseUrl}${path}`, {
    ...init,
    headers: { Accept: "application/json", ...init?.headers },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Mailpit ${path} failed: ${response.status} ${response.statusText}`);
  }
  return (await response.json()) as T;
}

export async function listMailpitMessages(limit = 50, start = 0): Promise<MailpitListResponse> {
  return mailpitFetch<MailpitListResponse>(`/api/v1/messages?limit=${limit}&start=${start}`);
}

// Mailpit search supports qualifiers like from:, to:, subject:, attachment:, tag:, read:false.
// The user types those literally and we forward them.
export async function searchMailpitMessages(query: string, limit = 50): Promise<MailpitListResponse> {
  const qs = new URLSearchParams({ query, limit: String(limit) });
  return mailpitFetch<MailpitListResponse>(`/api/v1/search?${qs}`);
}

export async function getMailpitMessage(id: string): Promise<MailpitMessage> {
  return mailpitFetch<MailpitMessage>(`/api/v1/message/${encodeURIComponent(id)}`);
}

export async function getMailpitInfo(): Promise<MailpitInfo> {
  return mailpitFetch<MailpitInfo>(`/api/v1/info`);
}

export async function listMailpitTags(): Promise<string[]> {
  return mailpitFetch<string[]>(`/api/v1/tags`);
}

async function mailpitBulk(method: "PUT" | "DELETE", body: Record<string, unknown>): Promise<void> {
  const response = await fetch(`${env.mailpitBaseUrl}/api/v1/messages`, {
    method,
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Mailpit ${method} /messages failed: ${response.status} ${response.statusText}`);
  }
}

export async function setMailpitRead(ids: string[], read: boolean): Promise<void> {
  return mailpitBulk("PUT", { IDs: ids, Read: read });
}

export async function deleteMailpitMessages(ids: string[]): Promise<void> {
  return mailpitBulk("DELETE", { IDs: ids });
}

export async function setMailpitTags(ids: string[], tags: string[]): Promise<void> {
  const response = await fetch(`${env.mailpitBaseUrl}/api/v1/tags`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ IDs: ids, Tags: tags }),
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Mailpit PUT /tags failed: ${response.status} ${response.statusText}`);
  }
}

export async function getMailpitRawEml(id: string): Promise<string> {
  const response = await fetch(`${env.mailpitBaseUrl}/api/v1/message/${encodeURIComponent(id)}/raw`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Mailpit raw failed: ${response.status} ${response.statusText}`);
  }
  return response.text();
}

// Streamable response, used by the proxy route to pass attachment bytes through.
export async function fetchMailpitPart(id: string, partId: string): Promise<Response> {
  return fetch(`${env.mailpitBaseUrl}/api/v1/message/${encodeURIComponent(id)}/part/${encodeURIComponent(partId)}`, {
    cache: "no-store",
  });
}

export async function fetchMailpitRaw(id: string): Promise<Response> {
  return fetch(`${env.mailpitBaseUrl}/api/v1/message/${encodeURIComponent(id)}/raw`, { cache: "no-store" });
}

export function mailpitMessageHtmlUrl(id: string): string {
  return `${env.mailpitBaseUrl}/view/${encodeURIComponent(id)}.html`;
}
