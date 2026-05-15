import Link from "next/link";
import { prisma } from "@/lib/prisma";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { asFormData, sentimentTone } from "@/lib/incident-form";
import { formatDateTime } from "@/lib/utils";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";
export const metadata = { title: "Incidents" };

type SearchParams = Promise<{ category?: string; priority?: string }>;

export default async function IncidentsPage({ searchParams }: { searchParams: SearchParams }) {
  const sp = await searchParams;
  const category = sp.category?.trim() || undefined;
  const priority = sp.priority?.trim() || undefined;

  const incidents = await prisma.incidentForm.findMany({
    where: { ...(category ? { category } : {}), ...(priority ? { priority } : {}) },
    include: {
      generalInformation: true,
      transcriptions: { where: { langCode: { not: "nl" } }, take: 1 },
    },
    orderBy: { completedAt: "desc" },
    take: 200,
  });

  const facets = await prisma.incidentForm.groupBy({
    by: ["category", "priority"],
    _count: { _all: true },
  });
  const categories = uniq(facets.map((f) => f.category).filter(Boolean) as string[]);
  const priorities = uniq(facets.map((f) => f.priority).filter(Boolean) as string[]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-medium tracking-tight">Incidents</h1>
        <p className="text-sm text-muted-foreground">
          AI-extracted forms from analyzed calls. Filter by category or priority.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Filter label="Category" value={category} options={categories} param="category" sp={sp} />
        <Filter label="Priority" value={priority} options={priorities} param="priority" sp={sp} />
        {(category || priority) && (
          <Link href="/incidents" className="text-xs text-muted-foreground underline-offset-4 hover:underline">
            Clear filters
          </Link>
        )}
      </div>

      {incidents.length === 0 ? (
        <div className="rounded-md border border-border p-12 text-center text-sm text-muted-foreground">
          No incidents yet. <Link href="/upload" className="text-foreground underline underline-offset-4">Upload audio</Link> to run the pipeline.
        </div>
      ) : (
        <div className="rounded-md border border-border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Completed</TableHead>
                <TableHead>Caller</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Priority</TableHead>
                <TableHead>Sentiment</TableHead>
                <TableHead>Summary</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {incidents.map((inc) => {
                const data = asFormData(inc.generalInformation?.formData);
                const sentiment = inc.transcriptions[0]?.sentiment ?? data.customer_sentiment ?? null;
                const tone = sentimentTone(sentiment);
                const summary = data.call_summary || inc.transcriptions[0]?.summary || "—";
                return (
                  <TableRow key={inc.id}>
                    <TableCell>
                      <Link href={`/incidents/${inc.id}`} className="hover:underline">
                        {formatDateTime(inc.completedAt)}
                      </Link>
                    </TableCell>
                    <TableCell>{inc.generalInformation?.callerName || "—"}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{inc.category ?? "—"}</TableCell>
                    <TableCell>
                      <PriorityBadge priority={inc.priority} />
                    </TableCell>
                    <TableCell>
                      <span
                        className={cn(
                          "rounded-md border px-2 py-0.5 text-xs",
                          tone === "negative" && "border-foreground bg-foreground text-background",
                          tone === "positive" && "border-border",
                          tone === "neutral" && "border-border text-muted-foreground"
                        )}
                      >
                        {sentiment ?? "—"}
                      </span>
                    </TableCell>
                    <TableCell className="max-w-[420px] truncate text-xs text-muted-foreground">
                      {summary}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

function uniq<T>(arr: T[]): T[] {
  return Array.from(new Set(arr));
}

function PriorityBadge({ priority }: { priority: string | null }) {
  if (!priority) return <span className="text-xs text-muted-foreground">—</span>;
  const high = /high|urgent|p1/i.test(priority);
  return high ? <Badge variant="solid">{priority}</Badge> : <Badge variant="default">{priority}</Badge>;
}

function Filter({
  label,
  value,
  options,
  param,
  sp,
}: {
  label: string;
  value: string | undefined;
  options: string[];
  param: "category" | "priority";
  sp: { category?: string; priority?: string };
}) {
  if (options.length === 0) return null;
  return (
    <div className="flex items-center gap-1 rounded-md border border-border p-0.5">
      <span className="px-2 text-xs uppercase tracking-wide text-muted-foreground">{label}</span>
      {options.map((opt) => {
        const next = { ...sp, [param]: opt };
        const isActive = value === opt;
        const params = new URLSearchParams(
          Object.entries(next).filter(([, v]) => Boolean(v)) as [string, string][]
        ).toString();
        return (
          <Link
            key={opt}
            href={`/incidents${params ? `?${params}` : ""}`}
            className={cn(
              "rounded px-2 py-0.5 text-xs",
              isActive ? "bg-foreground text-background" : "text-muted-foreground hover:text-foreground"
            )}
          >
            {opt}
          </Link>
        );
      })}
    </div>
  );
}
