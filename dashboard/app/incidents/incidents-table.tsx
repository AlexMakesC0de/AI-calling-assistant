"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Phone, MessageCircle, Mail } from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { TimeAgo } from "@/components/time-ago";
import { updateIncidentStatusAction } from "./actions";

type IncidentRow = {
  id: number;
  completedAt: string;
  callerName: string;
  category: string;
  priority: string;
  sentiment: string;
  sentimentTone: "positive" | "negative" | "neutral";
  summary: string;
  sourceType: string | undefined;
};

function SourceIcon({ sourceType }: { sourceType: string | undefined }) {
  const iconClass = "h-3.5 w-3.5 text-muted-foreground";
  switch (sourceType) {
    case "twilio_call": return <span title="Call"><Phone className={iconClass} /></span>;
    case "whatsapp_text": return <span title="WhatsApp"><MessageCircle className={iconClass} /></span>;
    case "outlook_email":
    case "gmail_email": return <span title="Email"><Mail className={iconClass} /></span>;
    default: return <span className="text-xs text-muted-foreground">—</span>;
  }
}

function PriorityBadge({ priority }: { priority: string | null }) {
  if (!priority) return <span className="text-xs text-muted-foreground">—</span>;
  const high = /high|urgent|p1/i.test(priority);
  return high ? <Badge variant="solid">{priority}</Badge> : <Badge variant="default">{priority}</Badge>;
}

export function IncidentsTable({ incidents }: { incidents: IncidentRow[] }) {
  const router = useRouter();
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [isPending, startTransition] = useTransition();

  const toggleSelect = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (selectedIds.size === incidents.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(incidents.map((i) => i.id)));
    }
  };

  const handleStatusUpdate = (status: string) => {
    const ids = Array.from(selectedIds);
    startTransition(async () => {
      const result = await updateIncidentStatusAction(ids, status);
      if (result.ok) {
        toast.success(`${ids.length} incident(s) marked as "${status}"`);
        setSelectedIds(new Set());
      } else {
        toast.error(result.error ?? "Failed to update");
      }
    });
  };

  return (
    <div className="space-y-2">
      {selectedIds.size > 0 && (
        <div className="flex items-center gap-3 rounded-md border border-border bg-muted/30 px-4 py-2">
          <span className="text-sm text-muted-foreground">{selectedIds.size} selected</span>
          <Button
            variant="outline"
            size="sm"
            disabled={isPending}
            onClick={() => handleStatusUpdate("resolved")}
          >
            Mark resolved
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={isPending}
            onClick={() => handleStatusUpdate("open")}
          >
            Mark open
          </Button>
        </div>
      )}
      <div className="rounded-md border border-border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-8">
                <input
                  type="checkbox"
                  checked={selectedIds.size === incidents.length && incidents.length > 0}
                  onChange={toggleAll}
                  className="h-4 w-4 cursor-pointer rounded border-border"
                  aria-label="Select all"
                />
              </TableHead>
              <TableHead className="w-10">Source</TableHead>
              <TableHead>Completed</TableHead>
              <TableHead>Caller</TableHead>
              <TableHead>Category</TableHead>
              <TableHead>Priority</TableHead>
              <TableHead>Sentiment</TableHead>
              <TableHead>Summary</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {incidents.map((inc) => (
              <TableRow
                key={inc.id}
                className={cn("cursor-pointer", selectedIds.has(inc.id) && "bg-muted/20")}
                onClick={() => router.push(`/incidents/${inc.id}`)}
              >
                <TableCell onClick={(e) => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    checked={selectedIds.has(inc.id)}
                    onChange={() => toggleSelect(inc.id)}
                    className="h-4 w-4 cursor-pointer rounded border-border"
                    aria-label={`Select incident ${inc.id}`}
                  />
                </TableCell>
                <TableCell>
                  <SourceIcon sourceType={inc.sourceType} />
                </TableCell>
                <TableCell>
                  <TimeAgo date={inc.completedAt} />
                </TableCell>
                <TableCell>{inc.callerName}</TableCell>
                <TableCell className="text-xs text-muted-foreground">{inc.category}</TableCell>
                <TableCell>
                  <PriorityBadge priority={inc.priority || null} />
                </TableCell>
                <TableCell>
                  <span
                    className={cn(
                      "rounded-md border px-2 py-0.5 text-xs",
                      inc.sentimentTone === "negative" && "border-foreground bg-foreground text-background",
                      inc.sentimentTone === "positive" && "border-border",
                      inc.sentimentTone === "neutral" && "border-border text-muted-foreground"
                    )}
                  >
                    {inc.sentiment}
                  </span>
                </TableCell>
                <TableCell className="max-w-[420px] truncate text-xs text-muted-foreground">
                  {inc.summary}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
