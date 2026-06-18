import Link from "next/link";
import { AlertTriangle } from "lucide-react";
import { prisma } from "@/lib/prisma";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { asFormData, sentimentTone } from "@/lib/incident-form";
import { cn } from "@/lib/utils";
import { EmptyState } from "@/components/empty-state";
import { IncidentsTable } from "./incidents-table";

export const dynamic = "force-dynamic";
export const metadata = { title: "Incidents" };

const PAGE_SIZE = 50;

type SearchParams = Promise<{ category?: string; priority?: string; q?: string; cursor?: string }>;

export default async function IncidentsPage({ searchParams }: { searchParams: SearchParams }) {
  const sp = await searchParams;
  const category = sp.category?.trim() || undefined;
  const priority = sp.priority?.trim() || undefined;
  const query = sp.q?.trim() || undefined;
  const cursorId = sp.cursor ? Number(sp.cursor) : undefined;

  const incidents = await prisma.incidentForm.findMany({
    where: {
      ...(category ? { category } : {}),
      ...(priority ? { priority } : {}),
      ...(query ? { generalInformation: { callerName: { contains: query, mode: "insensitive" as const } } } : {}),
    },
    include: {
      generalInformation: true,
      transcriptions: { where: { langCode: { not: "nl" } }, take: 1 },
    },
    orderBy: { completedAt: "desc" },
    take: PAGE_SIZE + 1,
    ...(cursorId ? { cursor: { id: cursorId }, skip: 1 } : {}),
  });

  const hasMore = incidents.length > PAGE_SIZE;
  const visibleIncidents = hasMore ? incidents.slice(0, PAGE_SIZE) : incidents;
  const nextCursor = hasMore ? visibleIncidents[visibleIncidents.length - 1]?.id : undefined;

  const incidentIds = visibleIncidents.map((inc) => inc.id);
  const sourceRows = incidentIds.length > 0
    ? await prisma.$queryRaw<{ incident_form_id: number; source_type: string }[]>`
        SELECT incident_form_id, source_type FROM content_analysis
        WHERE incident_form_id = ANY(${incidentIds}) AND pipeline_status = 'completed'
      `
    : [];
  const sourceMap = new Map(sourceRows.map((r) => [r.incident_form_id, r.source_type]));

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
        <form action="/incidents" className="flex items-center gap-2">
          {category && <input type="hidden" name="category" value={category} />}
          {priority && <input type="hidden" name="priority" value={priority} />}
          <Input name="q" defaultValue={query ?? ""} placeholder="Search by caller name…" className="h-8 w-56 text-sm" />
          <Button type="submit" variant="outline" size="sm">Search</Button>
        </form>
        <Filter label="Category" value={category} options={categories} param="category" sp={sp} />
        <Filter label="Priority" value={priority} options={priorities} param="priority" sp={sp} />
        {(category || priority || query) && (
          <Link href="/incidents" className="text-xs text-muted-foreground underline-offset-4 hover:underline">
            Clear filters
          </Link>
        )}
      </div>

      {visibleIncidents.length === 0 ? (
        <EmptyState
          icon={AlertTriangle}
          title="No incidents yet."
          description="Upload audio to run the analysis pipeline."
          action={{ label: "Upload audio", href: "/upload" }}
        />
      ) : (
        <IncidentsTable
          incidents={visibleIncidents.map((inc) => {
            const data = asFormData(inc.generalInformation?.formData);
            const sentiment = inc.transcriptions[0]?.sentiment ?? data.customer_sentiment ?? null;
            const tone = sentimentTone(sentiment);
            return {
              id: inc.id,
              completedAt: inc.completedAt instanceof Date ? inc.completedAt.toISOString() : String(inc.completedAt),
              callerName: inc.generalInformation?.callerName || "—",
              category: inc.category ?? "—",
              priority: inc.priority ?? "",
              sentiment: sentiment ?? "—",
              sentimentTone: tone,
              summary: data.call_summary || inc.transcriptions[0]?.summary || "—",
              sourceType: sourceMap.get(inc.id),
            };
          })}
        />
      )}

      {hasMore && nextCursor && (
        <div className="text-center">
          <Link
            href={`/incidents?${new URLSearchParams(
              Object.entries({ category, priority, q: query, cursor: String(nextCursor) }).filter(([, v]) => Boolean(v)) as [string, string][]
            ).toString()}`}
            className="inline-flex items-center gap-1 rounded-md border border-border px-4 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            Load more
          </Link>
        </div>
      )}
    </div>
  );
}

function uniq<T>(arr: T[]): T[] {
  return Array.from(new Set(arr));
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
