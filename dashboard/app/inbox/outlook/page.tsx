import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { InboxTabs } from "@/components/inbox-tabs";
import {
  flattenAddresses,
  listOutlookMessages,
  outlookConfigured,
  type OutlookMessageSummary,
} from "@/lib/outlook";
import { getValidAccessToken, getStoredToken } from "@/lib/outlook-oauth";
import { getValidGmailToken, getStoredGmailToken } from "@/lib/gmail-oauth";
import { getSession } from "@/lib/auth";
import { env } from "@/lib/env";
import { formatDateTime, cn } from "@/lib/utils";
import { DisconnectButton } from "./disconnect-button";

export const dynamic = "force-dynamic";
export const metadata = { title: "Inbox · Email" };

type SearchParams = Promise<{ q?: string; error?: string }>;

type EmailMessage = {
  id: string;
  subject: string;
  bodyPreview: string;
  from: string;
  fromName?: string;
  receivedAt: string;
  isRead: boolean;
  hasAttachments: boolean;
  importance?: string;
  provider: "microsoft" | "google";
};

async function listMicrosoftMessages(accountId: number, opts: { top: number; search?: string }): Promise<OutlookMessageSummary[] | null> {
  const creds = await getValidAccessToken(accountId);
  if (!creds) return null;

  const top = Math.min(Math.max(opts.top, 1), 100);
  const select = [
    "id", "subject", "bodyPreview", "from", "toRecipients",
    "receivedDateTime", "isRead", "hasAttachments", "importance", "webLink",
  ].join(",");

  const params = new URLSearchParams({ $top: String(top), $select: select });
  const headers: Record<string, string> = {
    Authorization: `Bearer ${creds.token}`,
    Accept: "application/json",
  };

  if (opts.search?.trim()) {
    params.set("$search", `"${opts.search.trim().replace(/"/g, '\\"')}"`);
    headers["ConsistencyLevel"] = "eventual";
  } else {
    params.set("$orderby", "receivedDateTime desc");
  }
  const path = `/me/mailFolders/Inbox/messages?${params}`;

  const res = await fetch(`https://graph.microsoft.com/v1.0${path}`, {
    headers,
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Graph ${res.status}: ${text.slice(0, 200)}`);
  }
  return ((await res.json()) as { value: OutlookMessageSummary[] }).value;
}

type GmailHeader = { name: string; value: string };
type GmailListItem = {
  id: string;
  snippet: string;
  payload: { headers: GmailHeader[] };
  labelIds: string[];
  internalDate: string;
};

async function listGmailMessages(accountId: number, opts: { top: number; search?: string }): Promise<EmailMessage[] | null> {
  const creds = await getValidGmailToken(accountId);
  if (!creds) return null;

  const params = new URLSearchParams({ maxResults: String(opts.top), labelIds: "INBOX" });
  if (opts.search?.trim()) params.set("q", opts.search.trim());

  const listRes = await fetch(
    `https://gmail.googleapis.com/gmail/v1/users/me/messages?${params}`,
    { headers: { Authorization: `Bearer ${creds.token}` }, cache: "no-store" },
  );
  if (!listRes.ok) throw new Error(`Gmail list error: ${listRes.status}`);
  const listData = (await listRes.json()) as { messages?: Array<{ id: string }> };
  if (!listData.messages?.length) return [];

  const details = await Promise.all(
    listData.messages.slice(0, opts.top).map(async (m) => {
      const res = await fetch(
        `https://gmail.googleapis.com/gmail/v1/users/me/messages/${m.id}?format=metadata&metadataHeaders=From&metadataHeaders=Subject&metadataHeaders=Date`,
        { headers: { Authorization: `Bearer ${creds.token}` }, cache: "no-store" },
      );
      if (!res.ok) return null;
      return res.json() as Promise<GmailListItem>;
    }),
  );

  return details.filter(Boolean).map((msg) => {
    const m = msg as GmailListItem;
    const hdr = (name: string) => m.payload.headers.find((h) => h.name.toLowerCase() === name.toLowerCase())?.value ?? "";
    const fromRaw = hdr("From");
    const fromMatch = fromRaw.match(/^(.+?)\s*<(.+?)>$/);
    return {
      id: m.id,
      subject: hdr("Subject") || "(no subject)",
      bodyPreview: m.snippet,
      from: fromMatch ? fromMatch[2] : fromRaw,
      fromName: fromMatch ? fromMatch[1].replace(/^"|"$/g, "") : undefined,
      receivedAt: new Date(Number(m.internalDate)).toISOString(),
      isRead: !m.labelIds.includes("UNREAD"),
      hasAttachments: false,
      provider: "google" as const,
    };
  });
}

export default async function EmailInboxPage({ searchParams }: { searchParams: SearchParams }) {
  const sp = await searchParams;
  const query = sp.q?.trim() ?? "";
  const oauthError = sp.error;

  const session = await getSession();
  const hasAppLevel = outlookConfigured();
  const hasMicrosoftId = Boolean(env.outlook.clientId);
  const hasGoogleId = env.google.configured;

  const msToken = session ? await getStoredToken(session.accountId) : null;
  const gmailToken = session ? await getStoredGmailToken(session.accountId) : null;

  const msConnected = Boolean(msToken);
  const gmailConnected = Boolean(gmailToken);
  const anyConnected = msConnected || gmailConnected || hasAppLevel;
  const connectedProvider = msConnected ? "microsoft" : gmailConnected ? "google" : hasAppLevel ? "microsoft-app" : null;

  let messages: EmailMessage[] = [];
  let unreadCount = 0;
  let error: string | null = oauthError ?? null;

  if (msConnected && session) {
    try {
      const result = await listMicrosoftMessages(session.accountId, { top: 50, search: query || undefined });
      if (result) {
        messages = result.map((m) => ({
          id: m.id,
          subject: m.subject || "(no subject)",
          bodyPreview: m.bodyPreview,
          from: m.from?.emailAddress?.address ?? "",
          fromName: m.from?.emailAddress?.name ?? undefined,
          receivedAt: m.receivedDateTime,
          isRead: m.isRead,
          hasAttachments: m.hasAttachments,
          importance: m.importance,
          provider: "microsoft" as const,
        }));
        unreadCount = messages.filter((m) => !m.isRead).length;
      } else {
        error = "Your Microsoft connection expired. Please reconnect.";
      }
    } catch (err) {
      error = err instanceof Error ? err.message : String(err);
    }
  } else if (gmailConnected && session) {
    try {
      const result = await listGmailMessages(session.accountId, { top: 50, search: query || undefined });
      if (result) {
        messages = result;
        unreadCount = messages.filter((m) => !m.isRead).length;
      } else {
        error = "Your Gmail connection expired. Please reconnect.";
      }
    } catch (err) {
      error = err instanceof Error ? err.message : String(err);
    }
  } else if (hasAppLevel) {
    try {
      const list = await listOutlookMessages({ top: 50, search: query || undefined });
      messages = list.value.map((m) => ({
        id: m.id,
        subject: m.subject || "(no subject)",
        bodyPreview: m.bodyPreview,
        from: m.from?.emailAddress?.address ?? "",
        fromName: m.from?.emailAddress?.name ?? undefined,
        receivedAt: m.receivedDateTime,
        isRead: m.isRead,
        hasAttachments: m.hasAttachments,
        importance: m.importance,
        provider: "microsoft" as const,
      }));
      unreadCount = messages.filter((m) => !m.isRead).length;
    } catch (err) {
      error = err instanceof Error ? err.message : String(err);
    }
  }

  const showConnect = !anyConnected && (hasMicrosoftId || hasGoogleId);
  const connectedEmail = msConnected ? msToken?.mailbox_email : gmailConnected ? gmailToken?.mailbox_email : null;

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-medium tracking-tight">Inbox</h1>
          {connectedEmail && (
            <p className="text-sm text-muted-foreground">
              Connected as <span className="font-mono text-xs">{connectedEmail}</span>
              {connectedProvider === "microsoft" && <span className="ml-1 text-xs">(Microsoft)</span>}
              {connectedProvider === "google" && <span className="ml-1 text-xs">(Gmail)</span>}
            </p>
          )}
          {connectedProvider === "microsoft-app" && (
            <p className="text-sm text-muted-foreground">
              Reading via Microsoft Graph (app-level).
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {msConnected && <DisconnectButton provider="microsoft" />}
          {gmailConnected && <DisconnectButton provider="google" />}
        </div>
      </div>

      <InboxTabs active="outlook" outlookConfigured={anyConnected} outlookUnread={unreadCount} />

      {showConnect && !error && (
        <Card>
          <CardHeader>
            <CardTitle>Connect your email</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Sign in with your email provider to view your inbox in the dashboard.
            </p>
            <div className="flex flex-wrap gap-3">
              {hasMicrosoftId && (
                <Button asChild variant="outline">
                  <a href="/api/outlook/connect" className="gap-2">
                    <svg viewBox="0 0 23 23" className="h-4 w-4" aria-hidden>
                      <path fill="#f35325" d="M1 1h10v10H1z" />
                      <path fill="#81bc06" d="M12 1h10v10H12z" />
                      <path fill="#05a6f0" d="M1 12h10v10H1z" />
                      <path fill="#ffba08" d="M12 12h10v10H12z" />
                    </svg>
                    Sign in with Microsoft
                  </a>
                </Button>
              )}
              {hasGoogleId && (
                <Button asChild variant="outline">
                  <a href="/api/gmail/connect" className="gap-2">
                    <svg viewBox="0 0 24 24" className="h-4 w-4" aria-hidden>
                      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" />
                      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                    </svg>
                    Sign in with Google
                  </a>
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {!anyConnected && !hasMicrosoftId && !hasGoogleId && (
        <Card>
          <CardHeader>
            <CardTitle>Email not configured</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <p>
              Set <code className="font-mono">OUTLOOK_CLIENT_ID</code> for Microsoft
              or <code className="font-mono">GOOGLE_CLIENT_ID</code> / <code className="font-mono">GOOGLE_CLIENT_SECRET</code> for
              Gmail to enable email integration.
            </p>
          </CardContent>
        </Card>
      )}

      {error && (
        <Card>
          <CardHeader>
            <CardTitle>{anyConnected ? "Email error" : "Connection error"}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="rounded-md bg-destructive px-3 py-2 text-xs text-destructive-foreground">{error}</p>
          </CardContent>
        </Card>
      )}

      {anyConnected && (
        <>
          <form className="flex gap-2">
            <Input
              name="q"
              defaultValue={query}
              placeholder={connectedProvider === "google" ? "Search Gmail..." : 'Search Outlook (e.g. from:"alice@x.com")...'}
              className="font-mono text-sm"
            />
            <Button type="submit" variant="outline">
              Search
            </Button>
            {query ? (
              <Button asChild variant="ghost">
                <Link href="/inbox/outlook">Clear</Link>
              </Button>
            ) : null}
          </form>

          {!error && messages.length === 0 ? (
            <div className="rounded-md border border-border p-12 text-center text-sm text-muted-foreground">
              {query ? "No matches." : "No messages in this folder."}
            </div>
          ) : !error ? (
            <div className="divide-y divide-border rounded-md border border-border">
              {messages.map((msg) => {
                const detailHref = msg.provider === "google"
                  ? `/inbox/outlook/gmail-${encodeURIComponent(msg.id)}`
                  : `/inbox/outlook/${encodeURIComponent(msg.id)}`;
                return (
                  <Link
                    key={msg.id}
                    href={detailHref}
                    className={cn(
                      "flex items-start gap-3 px-3 py-3 hover:bg-muted/40",
                      !msg.isRead && "bg-muted/20",
                    )}
                  >
                    <div className="hidden w-40 shrink-0 text-xs text-muted-foreground md:block">
                      {formatDateTime(msg.receivedAt)}
                    </div>
                    <div className="hidden w-56 shrink-0 truncate font-mono text-xs text-muted-foreground sm:block">
                      {msg.from || "—"}
                    </div>
                    <div className="min-w-0 flex-1 space-y-1">
                      <div className="flex items-center gap-2">
                        {!msg.isRead ? <span className="h-1.5 w-1.5 rounded-full bg-foreground" aria-label="unread" /> : null}
                        <span className={cn("truncate text-sm", !msg.isRead && "font-medium")}>
                          {msg.subject}
                        </span>
                        {msg.importance === "high" ? <Badge variant="solid">high</Badge> : null}
                      </div>
                      {msg.bodyPreview ? (
                        <p className="line-clamp-1 text-xs text-muted-foreground">{msg.bodyPreview}</p>
                      ) : null}
                    </div>
                    {msg.hasAttachments ? (
                      <span className="ml-auto shrink-0 text-xs text-muted-foreground">attached</span>
                    ) : null}
                  </Link>
                );
              })}
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}
