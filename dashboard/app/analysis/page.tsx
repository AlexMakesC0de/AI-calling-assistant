import Link from "next/link";
import { Phone, MessageCircle, Mail } from "lucide-react";
import { prisma } from "@/lib/prisma";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { TimeAgo } from "@/components/time-ago";
import { EmptyState } from "@/components/empty-state";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";
export const metadata = { title: "Analysis" };

type SearchParams = Promise<{ status?: string; source?: string }>;

type AnalysisRow = {
  id: number;
  source_type: string;
  source_id: string;
  pipeline_status: string;
  classification_label: string | null;
  classification_confidence: number | null;
  incident_form_id: number | null;
  content_preview: string | null;
  sender: string | null;
  analyzed_at: Date;
};

function SourceIcon({ sourceType }: { sourceType: string }) {
  const cls = "h-3.5 w-3.5 text-muted-foreground";
  switch (sourceType) {
    case "twilio_call": return <Phone className={cls} title="Call" />;
    case "whatsapp_text": return <MessageCircle className={cls} title="WhatsApp" />;
    case "outlook_email":
    case "gmail_email": return <Mail className={cls} title="Email" />;
    default: return <span className="text-xs text-muted-foreground">?</span>;
  }
}

function labelColor(label: string) {
  switch (label) {
    case "support": return "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400";
    case "not_support": return "bg-zinc-100 text-zinc-600 dark:bg-zinc-800/50 dark:text-zinc-400";
    case "unclear": return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400";
    default: return "bg-zinc-100 text-zinc-600";
  }
}

export default async function AnalysisPage({ searchParams }: { searchParams: SearchParams }) {
  const sp = await searchParams;
  const statusFilter = sp.status?.trim() || undefined;
  const sourceFilter = sp.source?.trim() || undefined;

  const conditions: string[] = ["1=1"];
  if (statusFilter) conditions.push(`pipeline_status = '${statusFilter.replace(/'/g, "")}'`);
  if (sourceFilter) conditions.push(`source_type = '${sourceFilter.replace(/'/g, "")}'`);

  const rows = await prisma.$queryRawUnsafe<AnalysisRow[]>(
    `SELECT id, source_type, source_id, pipeline_status, classification_label,
            classification_confidence, incident_form_id, content_preview, sender, analyzed_at
     FROM content_analysis
     WHERE ${conditions.join(" AND ")}
     ORDER BY analyzed_at DESC
     LIMIT 100`,
  );

  const statuses = ["pending", "completed", "failed"];
  const sources = ["twilio_call", "whatsapp_text", "outlook_email", "gmail_email"];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-medium tracking-tight">Analysis History</h1>
        <p className="text-sm text-muted-foreground">
          All AI analysis runs across calls, WhatsApp, and email.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <FilterGroup label="Status" options={statuses} current={statusFilter} param="status" sp={sp} />
        <FilterGroup label="Source" options={sources} current={sourceFilter} param="source" sp={sp} displayMap={{
          twilio_call: "Call",
          whatsapp_text: "WhatsApp",
          outlook_email: "Outlook",
          gmail_email: "Gmail",
        }} />
        {(statusFilter || sourceFilter) && (
          <Link href="/analysis" className="text-xs text-muted-foreground underline-offset-4 hover:underline">
            Clear filters
          </Link>
        )}
      </div>

      {rows.length === 0 ? (
        <EmptyState title="No analysis runs found." description="Trigger an analysis from any WhatsApp, call, or email detail page." />
      ) : (
        <div className="rounded-md border border-border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">Source</TableHead>
                <TableHead>When</TableHead>
                <TableHead>Sender</TableHead>
                <TableHead>Preview</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Classification</TableHead>
                <TableHead>Incident</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => (
                <TableRow key={row.id}>
                  <TableCell><SourceIcon sourceType={row.source_type} /></TableCell>
                  <TableCell><TimeAgo date={row.analyzed_at} /></TableCell>
                  <TableCell className="text-sm">{row.sender ?? "—"}</TableCell>
                  <TableCell className="max-w-[240px] truncate text-xs text-muted-foreground">
                    {row.content_preview ?? "—"}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={row.pipeline_status === "completed" ? "muted" : row.pipeline_status === "failed" ? "solid" : "default"}
                    >
                      {row.pipeline_status}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {row.classification_label ? (
                      <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium", labelColor(row.classification_label))}>
                        {row.classification_label.replace("_", " ")}
                        {row.classification_confidence != null && (
                          <span className="ml-1 opacity-60">{Math.round(row.classification_confidence * 100)}%</span>
                        )}
                      </span>
                    ) : "—"}
                  </TableCell>
                  <TableCell>
                    {row.incident_form_id ? (
                      <Link href={`/incidents/${row.incident_form_id}`} className="text-xs underline underline-offset-4 hover:text-foreground">
                        #{row.incident_form_id}
                      </Link>
                    ) : "—"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

function FilterGroup({
  label,
  options,
  current,
  param,
  sp,
  displayMap,
}: {
  label: string;
  options: string[];
  current: string | undefined;
  param: string;
  sp: Record<string, string | undefined>;
  displayMap?: Record<string, string>;
}) {
  return (
    <div className="flex items-center gap-1 rounded-md border border-border p-0.5">
      <span className="px-2 text-xs uppercase tracking-wide text-muted-foreground">{label}</span>
      {options.map((opt) => {
        const next = { ...sp, [param]: opt };
        const isActive = current === opt;
        const params = new URLSearchParams(
          Object.entries(next).filter(([, v]) => Boolean(v)) as [string, string][]
        ).toString();
        return (
          <Link
            key={opt}
            href={`/analysis${params ? `?${params}` : ""}`}
            className={cn(
              "rounded px-2 py-0.5 text-xs",
              isActive ? "bg-foreground text-background" : "text-muted-foreground hover:text-foreground"
            )}
          >
            {displayMap?.[opt] ?? opt}
          </Link>
        );
      })}
    </div>
  );
}
