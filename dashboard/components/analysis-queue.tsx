"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { Loader2, Phone, MessageCircle, Mail, Check, X } from "lucide-react";

type ActiveItem = {
  sourceType: string;
  sourceId: string;
  pipelineStatus: string;
  pipelineStep: string | null;
  contentPreview: string | null;
  sender: string | null;
  classificationLabel: string | null;
  incidentFormId: number | null;
};

function sourceIcon(type: string) {
  switch (type) {
    case "twilio_call": return <Phone className="h-3 w-3" />;
    case "whatsapp_text": return <MessageCircle className="h-3 w-3" />;
    case "outlook_email":
    case "gmail_email": return <Mail className="h-3 w-3" />;
    default: return null;
  }
}

function sourceLink(type: string, id: string): string {
  switch (type) {
    case "outlook_email":
    case "gmail_email": return `/inbox/outlook/${type === "gmail_email" ? `gmail-${id}` : id}`;
    default: return "#";
  }
}

function stepText(status: string, step: string | null): string {
  if (status === "completed") return "Done";
  if (status === "failed") return "Failed";
  switch (step) {
    case "classifying": return "Classifying…";
    case "saving": return "Creating incident…";
    default: return "Queued…";
  }
}

export function AnalysisQueue() {
  const [items, setItems] = useState<ActiveItem[]>([]);
  const [open, setOpen] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch("/api/analysis/active");
        if (res.ok) {
          const data = await res.json();
          setItems(data);
        }
      } catch {
        // silent
      }
    };

    poll();
    intervalRef.current = setInterval(poll, 5000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, []);

  const pendingCount = items.filter((i) => i.pipelineStatus === "pending").length;

  if (items.length === 0) return null;

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="relative flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
      >
        {pendingCount > 0 ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <Check className="h-3.5 w-3.5 text-green-500" />
        )}
        <span>{pendingCount > 0 ? `${pendingCount} analyzing` : `${items.length} recent`}</span>
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full z-50 mt-1 w-80 rounded-md border border-border bg-background shadow-lg">
            <div className="border-b border-border px-3 py-2">
              <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Analysis Queue
              </h3>
            </div>
            <div className="max-h-64 overflow-y-auto divide-y divide-border">
              {items.map((item) => (
                <div key={`${item.sourceType}-${item.sourceId}`} className="flex items-start gap-2 px-3 py-2">
                  <div className="mt-0.5 text-muted-foreground">
                    {item.pipelineStatus === "pending" ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : item.pipelineStatus === "failed" ? (
                      <X className="h-3 w-3 text-destructive" />
                    ) : (
                      <Check className="h-3 w-3 text-green-500" />
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      {sourceIcon(item.sourceType)}
                      <span className="truncate text-xs font-medium">
                        {item.sender || item.sourceId.slice(0, 20)}
                      </span>
                    </div>
                    <p className="truncate text-[11px] text-muted-foreground">
                      {item.contentPreview?.slice(0, 60) || "No preview"}
                    </p>
                    <div className="flex items-center gap-2 text-[11px]">
                      <span className={item.pipelineStatus === "failed" ? "text-destructive" : "text-muted-foreground"}>
                        {stepText(item.pipelineStatus, item.pipelineStep)}
                      </span>
                      {item.incidentFormId && (
                        <Link
                          href={`/incidents/${item.incidentFormId}`}
                          className="underline underline-offset-2 hover:text-foreground"
                          onClick={() => setOpen(false)}
                        >
                          #{item.incidentFormId}
                        </Link>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
