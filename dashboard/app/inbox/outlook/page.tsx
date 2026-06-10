import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { InboxTabs } from "@/components/inbox-tabs";
import {
  flattenAddresses,
  listOutlookMessages,
  outlookConfigured,
  type OutlookMessageSummary,
} from "@/lib/outlook";
import { formatDateTime } from "@/lib/utils";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";
export const metadata = { title: "Inbox · Outlook" };

type SearchParams = Promise<{ q?: string }>;

export default async function OutlookInboxPage({ searchParams }: { searchParams: SearchParams }) {
  const sp = await searchParams;
  const query = sp.q?.trim() ?? "";

  if (!outlookConfigured()) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-medium tracking-tight">Inbox</h1>
        </div>
        <InboxTabs active="outlook" outlookConfigured={false} />
        <Card>
          <CardHeader>
            <CardTitle>Outlook is not configured</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <p>
              Set the following environment variables on the dashboard service to enable read-only access
              to a shared Microsoft 365 mailbox:
            </p>
            <ul className="ml-4 list-disc space-y-1 font-mono text-xs">
              <li>OUTLOOK_TENANT_ID</li>
              <li>OUTLOOK_CLIENT_ID</li>
              <li>OUTLOOK_CLIENT_SECRET</li>
              <li>OUTLOOK_MAILBOX (the mailbox UPN, e.g. support@yourcompany.com)</li>
              <li>OUTLOOK_FOLDER (optional, defaults to &quot;Inbox&quot;)</li>
            </ul>
            <p className="text-xs text-muted-foreground">
              The app registration needs <code className="font-mono">Mail.Read</code> as an{" "}
              <strong>application</strong> permission, admin-consented. Client-credentials flow — no user
              login is involved.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  let messages: OutlookMessageSummary[] = [];
  let unreadCount = 0;
  let error: string | null = null;
  try {
    const list = await listOutlookMessages({ top: 50, search: query || undefined });
    messages = list.value;
    unreadCount = messages.filter((m) => !m.isRead).length;
  } catch (err) {
    error = err instanceof Error ? err.message : String(err);
  }

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-medium tracking-tight">Inbox</h1>
          <p className="text-sm text-muted-foreground">
            Reading <span className="font-mono text-xs">Outlook</span> via Microsoft Graph.
          </p>
        </div>
      </div>

      <InboxTabs active="outlook" outlookConfigured={true} outlookUnread={unreadCount} />

      <form className="flex gap-2">
        <Input
          name="q"
          defaultValue={query}
          placeholder='Search Outlook (e.g. from:"alice@x.com" subject:incident)…'
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

      {error ? (
        <Card>
          <CardHeader>
            <CardTitle>Outlook unreachable</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="rounded-md bg-destructive px-3 py-2 text-xs text-destructive-foreground">{error}</p>
          </CardContent>
        </Card>
      ) : messages.length === 0 ? (
        <div className="rounded-md border border-border p-12 text-center text-sm text-muted-foreground">
          {query ? "No matches in this folder." : "No messages in this folder."}
        </div>
      ) : (
        <div className="divide-y divide-border rounded-md border border-border">
          {messages.map((msg) => (
            <Link
              key={msg.id}
              href={`/inbox/outlook/${encodeURIComponent(msg.id)}`}
              className={cn(
                "flex items-start gap-3 px-3 py-3 hover:bg-muted/40",
                !msg.isRead && "bg-muted/20"
              )}
            >
              <div className="hidden w-40 shrink-0 text-xs text-muted-foreground md:block">
                {formatDateTime(msg.receivedDateTime)}
              </div>
              <div className="hidden w-56 shrink-0 truncate font-mono text-xs text-muted-foreground sm:block">
                {msg.from?.emailAddress?.address ?? "—"}
              </div>
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex items-center gap-2">
                  {!msg.isRead ? <span className="h-1.5 w-1.5 rounded-full bg-foreground" aria-label="unread" /> : null}
                  <span className={cn("truncate text-sm", !msg.isRead && "font-medium")}>
                    {msg.subject || "(no subject)"}
                  </span>
                  {msg.importance === "high" ? <Badge variant="solid">high</Badge> : null}
                </div>
                {msg.bodyPreview ? (
                  <p className="line-clamp-1 text-xs text-muted-foreground">{msg.bodyPreview}</p>
                ) : null}
                {msg.toRecipients && msg.toRecipients.length > 0 ? (
                  <p className="text-xs text-muted-foreground sm:hidden">
                    to {flattenAddresses(msg.toRecipients)}
                  </p>
                ) : null}
              </div>
              {msg.hasAttachments ? (
                <span className="ml-auto shrink-0 text-xs text-muted-foreground">attached</span>
              ) : null}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
