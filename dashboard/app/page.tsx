import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { StatCard } from "@/components/stat-card";
import { prisma } from "@/lib/prisma";
import { listMailpitMessages } from "@/lib/mailpit";
import { asFormData, sentimentTone } from "@/lib/incident-form";
import { cn } from "@/lib/utils";
import { TimeAgo } from "@/components/time-ago";

export const dynamic = "force-dynamic";

async function loadStats() {
  const since = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
  const [total, recent, byCategory, byPriority] = await Promise.all([
    prisma.incidentForm.count(),
    prisma.incidentForm.count({ where: { completedAt: { gte: since } } }),
    prisma.incidentForm.groupBy({ by: ["category"], _count: { _all: true }, orderBy: { _count: { id: "desc" } } }),
    prisma.incidentForm.groupBy({ by: ["priority"], _count: { _all: true }, orderBy: { _count: { id: "desc" } } }),
  ]);
  return { total, recent, byCategory, byPriority };
}

async function loadRecentIncidents() {
  return prisma.incidentForm.findMany({
    include: { generalInformation: true, transcriptions: { take: 1, where: { langCode: { not: "nl" } } } },
    orderBy: { completedAt: "desc" },
    take: 6,
  });
}

async function loadInbox() {
  try {
    const list = await listMailpitMessages(5);
    return { ok: true as const, total: list.total, unread: list.unread, messages: list.messages };
  } catch (err) {
    return { ok: false as const, error: err instanceof Error ? err.message : String(err) };
  }
}

export default async function OverviewPage() {
  const [stats, recent, inbox] = await Promise.all([loadStats(), loadRecentIncidents(), loadInbox()]);

  const sentimentCounts = countSentiments(recent);
  const topCategory = stats.byCategory[0]?.category ?? null;

  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-medium tracking-tight">Overview</h1>
          <p className="text-sm text-muted-foreground">
            AI-extracted incidents and dispatched emails across the support pipeline.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button asChild variant="outline">
            <Link href="/inbox">Open inbox</Link>
          </Button>
          <Button asChild>
            <Link href="/upload">Upload audio</Link>
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label="Incidents" value={stats.total} hint={`${stats.recent} in last 7d`} />
        <StatCard
          label="Inbox"
          value={inbox.ok ? inbox.total : "—"}
          hint={inbox.ok ? `${inbox.unread} unread` : "Mailpit unreachable"}
        />
        <StatCard label="Top category" value={topCategory ?? "—"} hint={`${stats.byCategory.length} distinct`} />
        <StatCard label="Top priority" value={stats.byPriority[0]?.priority ?? "—"} hint={`${stats.byPriority.length} distinct`} />
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        <Card className="md:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between space-y-0">
            <CardTitle>Recent incidents</CardTitle>
            <Link href="/incidents" className="text-xs text-muted-foreground hover:text-foreground">
              View all →
            </Link>
          </CardHeader>
          <CardContent className="divide-y divide-border p-0">
            {recent.length === 0 ? (
              <p className="px-6 py-8 text-sm text-muted-foreground">No incidents yet.</p>
            ) : (
              recent.map((inc) => {
                const data = asFormData(inc.generalInformation?.formData);
                const summary = data.call_summary || inc.transcriptions[0]?.summary || "—";
                const sentiment = inc.transcriptions[0]?.sentiment ?? data.customer_sentiment ?? null;
                const tone = sentimentTone(sentiment);
                return (
                  <Link
                    key={inc.id}
                    href={`/incidents/${inc.id}`}
                    className="flex items-start gap-4 px-6 py-3 hover:bg-muted/40"
                  >
                    <div className="w-32 shrink-0 text-xs text-muted-foreground">
                      <TimeAgo date={inc.completedAt} />
                    </div>
                    <div className="min-w-0 flex-1 space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">
                          {inc.generalInformation?.callerName || `Incident #${inc.id}`}
                        </span>
                        {inc.category ? (
                          <span className="text-xs text-muted-foreground">{inc.category}</span>
                        ) : null}
                        {inc.priority ? <Badge variant="default">{inc.priority}</Badge> : null}
                      </div>
                      <p className="line-clamp-1 text-xs text-muted-foreground">{summary}</p>
                    </div>
                    <span
                      className={cn(
                        "rounded-md border px-2 py-0.5 text-xs",
                        tone === "negative" && "border-foreground bg-foreground text-background",
                        tone !== "negative" && "border-border text-muted-foreground"
                      )}
                    >
                      {sentiment ?? "—"}
                    </span>
                  </Link>
                );
              })
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0">
            <CardTitle>Inbox</CardTitle>
            <Link href="/inbox" className="text-xs text-muted-foreground hover:text-foreground">
              Open →
            </Link>
          </CardHeader>
          <CardContent className="divide-y divide-border p-0">
            {!inbox.ok ? (
              <p className="px-6 py-8 text-xs text-muted-foreground">Mailpit unreachable: {inbox.error}</p>
            ) : inbox.messages.length === 0 ? (
              <p className="px-6 py-8 text-sm text-muted-foreground">No emails yet.</p>
            ) : (
              inbox.messages.map((m) => (
                <Link
                  key={m.ID}
                  href={`/inbox/${encodeURIComponent(m.ID)}`}
                  className={cn(
                    "block space-y-1 px-6 py-3 hover:bg-muted/40",
                    !m.Read && "bg-muted/20"
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-xs text-muted-foreground">{m.From.Address}</span>
                    {!m.Read ? <span className="h-1.5 w-1.5 rounded-full bg-foreground" /> : null}
                  </div>
                  <div className="truncate text-sm">{m.Subject || "(no subject)"}</div>
                </Link>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Sentiment in last {recent.length} incidents</CardTitle>
        </CardHeader>
        <CardContent>
          <SentimentBar counts={sentimentCounts} />
        </CardContent>
      </Card>
    </div>
  );
}

type SentimentCounts = { positive: number; neutral: number; negative: number; total: number };
function countSentiments(
  incidents: Array<{
    generalInformation?: { formData: unknown } | null;
    transcriptions: Array<{ sentiment: string | null }>;
  }>
): SentimentCounts {
  const out = { positive: 0, neutral: 0, negative: 0, total: 0 };
  for (const inc of incidents) {
    const data = asFormData(inc.generalInformation?.formData);
    const sentiment = inc.transcriptions[0]?.sentiment ?? data.customer_sentiment ?? null;
    out[sentimentTone(sentiment)] += 1;
    out.total += 1;
  }
  return out;
}

function SentimentBar({ counts }: { counts: SentimentCounts }) {
  if (counts.total === 0) return <p className="text-sm text-muted-foreground">No sentiment data yet.</p>;
  const segments = [
    { key: "positive" as const, label: "Positive", value: counts.positive, className: "bg-muted" },
    { key: "neutral" as const, label: "Neutral", value: counts.neutral, className: "bg-muted-foreground/40" },
    { key: "negative" as const, label: "Negative", value: counts.negative, className: "bg-foreground" },
  ];
  return (
    <div className="space-y-2">
      <div className="flex h-2 overflow-hidden rounded-md border border-border">
        {segments.map((seg) => {
          const pct = (seg.value / counts.total) * 100;
          return pct > 0 ? <div key={seg.key} className={seg.className} style={{ width: `${pct}%` }} /> : null;
        })}
      </div>
      <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
        {segments.map((seg) => (
          <span key={seg.key} className="flex items-center gap-1.5">
            <span className={cn("h-2 w-2 rounded-sm", seg.className)} />
            {seg.label}: <span className="tabular-nums text-foreground">{seg.value}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
