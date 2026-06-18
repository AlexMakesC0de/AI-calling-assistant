import { Skeleton } from "@/components/ui/skeleton";

export default function IncidentsLoading() {
  return (
    <div className="space-y-6">
      <div>
        <Skeleton className="h-8 w-28" />
        <Skeleton className="mt-2 h-4 w-72" />
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-8 w-40" />
      </div>
      <div className="rounded-md border border-border">
        <div className="border-b border-border px-4 py-3">
          <div className="flex gap-4">
            {["w-24", "w-20", "w-20", "w-16", "w-20", "w-64"].map((w, i) => (
              <Skeleton key={i} className={`h-4 ${w}`} />
            ))}
          </div>
        </div>
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="flex gap-4 border-b border-border px-4 py-3 last:border-0">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-5 w-16 rounded-full" />
            <Skeleton className="h-5 w-16 rounded-md" />
            <Skeleton className="h-4 w-64" />
          </div>
        ))}
      </div>
    </div>
  );
}
