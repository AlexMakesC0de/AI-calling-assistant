import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { InboxList } from "@/components/inbox-list";
import { InboxTabs } from "@/components/inbox-tabs";
import {
  listMailpitMessages,
  listMailpitTags,
  searchMailpitMessages,
  type MailpitListResponse,
} from "@/lib/mailpit";
import { outlookConfigured } from "@/lib/outlook";
import { getStoredToken } from "@/lib/outlook-oauth";
import { getSession } from "@/lib/auth";

export const dynamic = "force-dynamic";
export const metadata = { title: "Inbox" };

type SearchParams = Promise<{ q?: string }>;

export default async function InboxPage({ searchParams }: { searchParams: SearchParams }) {
  const sp = await searchParams;
  const query = sp.q?.trim() ?? "";
  const session = await getSession();
  const userToken = session ? await getStoredToken(session.accountId) : null;
  const hasOutlook = outlookConfigured() || Boolean(userToken);

  let response: MailpitListResponse | null = null;
  let tags: string[] = [];
  let error: string | null = null;
  try {
    [response, tags] = await Promise.all([
      query ? searchMailpitMessages(query, 100) : listMailpitMessages(100),
      listMailpitTags().catch(() => [] as string[]),
    ]);
  } catch (err) {
    error = err instanceof Error ? err.message : String(err);
  }

  if (error || !response) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-medium tracking-tight">Inbox</h1>
        </div>
        <InboxTabs active="mailpit" outlookConfigured={hasOutlook} />
        <Card>
          <CardHeader>
            <CardTitle>Mailpit unreachable</CardTitle>
            <CardDescription>
              Set <code className="font-mono">MAILPIT_URL</code> to a host the dashboard can reach (default
              <code className="font-mono"> http://localhost:8025</code>).
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="rounded-md bg-destructive px-3 py-2 text-sm text-destructive-foreground">
              {error ?? "Empty response."}
            </p>
            <p className="mt-3 text-xs text-muted-foreground">
              <Link className="underline underline-offset-4" href="/system">Open system status →</Link>
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <InboxList
      initialMessages={response.messages}
      total={response.total}
      unread={response.unread}
      query={query}
      knownTags={tags}
      tabs={
        <InboxTabs
          active="mailpit"
          outlookConfigured={hasOutlook}
          mailpitUnread={response.unread}
        />
      }
    />
  );
}
