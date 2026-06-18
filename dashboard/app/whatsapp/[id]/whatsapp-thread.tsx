"use client";

import { useState, useTransition, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { relativeTime, formatDateTime } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { CopyButton } from "@/components/copy-button";
import { WhatsAppAnalyzeWrapper } from "./whatsapp-analyze-wrapper";
import { analyzeWhatsAppBatchAction, type BatchAnalysisResult } from "../actions";

type MediaItem = { id: number; contentType: string; localPath: string | null };

type ThreadMsg = {
  id: number;
  direction: string;
  messageType: string;
  body: string | null;
  status: string;
  createdAt: string;
  incidentFormId: number | null;
  media: MediaItem[];
};

type AnalysisInfo = {
  label: string;
  incidentFormId: number | null;
};

type Props = {
  messages: ThreadMsg[];
  analysisMap: Record<string, AnalysisInfo>;
  contactPhone: string;
  contactName: string | null;
};

export function WhatsAppThread({ messages, analysisMap, contactPhone, contactName }: Props) {
  const [selectMode, setSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [isPending, startTransition] = useTransition();
  const [batchProgress, setBatchProgress] = useState<{ total: number; completed: number } | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const inboundTextIds = messages
    .filter((m) => m.messageType === "text" && m.body?.trim() && m.direction === "inbound")
    .map((m) => m.id);

  const unanalyzedIds = inboundTextIds.filter((id) => !analysisMap[String(id)]);

  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  const toggleSelect = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAll = () => {
    setSelectedIds(new Set(unanalyzedIds));
  };

  const startBatch = useCallback(() => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;

    startTransition(async () => {
      const result: BatchAnalysisResult = await analyzeWhatsAppBatchAction(ids);
      if (!result.started) {
        toast.error("Batch analysis failed", { description: "error" in result ? result.error : "Unknown error" });
        return;
      }

      const sourceIds = result.sourceIds;
      setBatchProgress({ total: sourceIds.length, completed: 0 });

      pollRef.current = setInterval(async () => {
        try {
          const res = await fetch(
            `/api/analysis/status?sourceType=whatsapp_text&sourceIds=${sourceIds.join(",")}`,
          );
          if (!res.ok) return;
          const data = await res.json();
          const done = (data as { pipelineStatus: string }[]).filter(
            (d) => d.pipelineStatus === "completed" || d.pipelineStatus === "failed",
          ).length;
          setBatchProgress({ total: sourceIds.length, completed: done });

          if (done >= sourceIds.length) {
            if (pollRef.current) clearInterval(pollRef.current);
            pollRef.current = null;
            setBatchProgress(null);
            setSelectMode(false);
            setSelectedIds(new Set());
            toast.success(`Batch analysis complete (${done} messages)`);
            window.location.reload();
          }
        } catch {
          // poll error, keep trying
        }
      }, 4000);
    });
  }, [selectedIds]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h1 className="text-2xl font-medium tracking-tight">
            {contactName || contactPhone}
          </h1>
          {contactName && (
            <p className="flex items-center gap-1.5 font-mono text-xs text-muted-foreground">
              {contactPhone} <CopyButton value={contactPhone} />
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {unanalyzedIds.length > 0 && (
            <Button
              variant={selectMode ? "default" : "outline"}
              size="sm"
              onClick={() => {
                setSelectMode(!selectMode);
                if (selectMode) setSelectedIds(new Set());
              }}
            >
              {selectMode ? "Cancel selection" : "Select messages"}
            </Button>
          )}
          <Link href="/whatsapp" className="text-sm text-muted-foreground hover:text-foreground">
            ← Back to conversations
          </Link>
        </div>
      </div>

      {selectMode && (
        <div className="flex items-center gap-3 rounded-md border border-border bg-muted/30 px-4 py-2">
          <Button variant="ghost" size="sm" onClick={selectAll}>
            Select all unanalyzed ({unanalyzedIds.length})
          </Button>
          <span className="text-sm text-muted-foreground">
            {selectedIds.size} selected
          </span>
          <Button
            size="sm"
            disabled={selectedIds.size === 0 || isPending || !!batchProgress}
            onClick={startBatch}
          >
            {isPending ? "Starting…" : batchProgress
              ? `Analyzing ${batchProgress.completed}/${batchProgress.total}…`
              : `Analyze selected (${selectedIds.size})`}
          </Button>
          {batchProgress && (
            <div className="flex-1">
              <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-foreground transition-all duration-500"
                  style={{ width: `${(batchProgress.completed / batchProgress.total) * 100}%` }}
                />
              </div>
            </div>
          )}
        </div>
      )}

      {messages.length === 0 ? (
        <div className="rounded-md border border-border p-12 text-center text-sm text-muted-foreground">
          No messages in this conversation.
        </div>
      ) : (
        <div className="space-y-3">
          {messages.map((msg) => {
            const isOutbound = msg.direction === "outbound";
            const isInboundText = msg.messageType === "text" && msg.body?.trim() && !isOutbound;
            const existingAnalysis = analysisMap[String(msg.id)];
            const analysisProps = existingAnalysis ? {
              label: existingAnalysis.label,
              confidence: 0,
              reason: "",
              incidentFormId: existingAnalysis.incidentFormId,
              pipelineStatus: "completed" as const,
              errorMessage: null,
            } : null;
            const isSelectable = selectMode && isInboundText && !existingAnalysis;

            return (
              <div key={msg.id} className={cn("flex", isOutbound ? "justify-end" : "justify-start")}>
                {isSelectable && (
                  <div className="flex items-center pr-2">
                    <input
                      type="checkbox"
                      checked={selectedIds.has(msg.id)}
                      onChange={() => toggleSelect(msg.id)}
                      className="h-4 w-4 cursor-pointer rounded border-border"
                      aria-label={`Select message ${msg.id}`}
                    />
                  </div>
                )}
                <div
                  className={cn(
                    "max-w-[75%] space-y-1.5 rounded-2xl px-4 py-3 text-sm",
                    isOutbound
                      ? "rounded-tr-sm bg-foreground text-background"
                      : "rounded-tl-sm border border-border bg-muted/30"
                  )}
                >
                  {msg.messageType !== "text" && (
                    <div>
                      <span
                        className={cn(
                          "inline-block rounded-full px-2 py-0.5 text-xs font-medium",
                          isOutbound ? "bg-background/20" : "border border-border bg-background text-foreground"
                        )}
                      >
                        {({ voice_note: "Voice note", image: "Image", document: "Document", video: "Video", sticker: "Sticker", location: "Location" } as Record<string, string>)[msg.messageType] ?? msg.messageType}
                      </span>
                    </div>
                  )}

                  {msg.body && (
                    <p className="whitespace-pre-wrap leading-relaxed">{msg.body}</p>
                  )}

                  {msg.media.length > 0 && (
                    <div className="space-y-1">
                      {msg.media.map((m) => (
                        <MediaRow key={m.id} media={m} outbound={isOutbound} />
                      ))}
                    </div>
                  )}

                  {msg.messageType === "voice_note" && msg.incidentFormId && (
                    <div>
                      <Link
                        href={`/incidents/${msg.incidentFormId}`}
                        className={cn(
                          "text-xs underline underline-offset-4",
                          isOutbound ? "text-background/70 hover:text-background" : "text-muted-foreground hover:text-foreground"
                        )}
                      >
                        View incident #{msg.incidentFormId} →
                      </Link>
                    </div>
                  )}

                  {msg.messageType === "voice_note" && !msg.incidentFormId && (
                    <p className={cn("text-xs", isOutbound ? "text-background/60" : "text-muted-foreground")}>
                      Processing…
                    </p>
                  )}

                  {isInboundText && !selectMode && (
                    <div className="pt-1">
                      <WhatsAppAnalyzeWrapper messageId={msg.id} existingAnalysis={analysisProps} />
                    </div>
                  )}

                  {isInboundText && msg.incidentFormId && !existingAnalysis && (
                    <div>
                      <Link
                        href={`/incidents/${msg.incidentFormId}`}
                        className="text-xs underline underline-offset-4 text-muted-foreground hover:text-foreground"
                      >
                        View incident #{msg.incidentFormId} →
                      </Link>
                    </div>
                  )}

                  <div
                    className={cn(
                      "flex items-center gap-2 text-xs",
                      isOutbound ? "justify-end text-background/60" : "text-muted-foreground"
                    )}
                  >
                    <TooltipProvider delayDuration={200}>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span className="cursor-default">{relativeTime(msg.createdAt)}</span>
                        </TooltipTrigger>
                        <TooltipContent><p>{formatDateTime(msg.createdAt)}</p></TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                    {isOutbound && <StatusDot status={msg.status} />}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function MediaRow({ media, outbound }: { media: MediaItem; outbound: boolean }) {
  const isImage = media.contentType.startsWith("image/");
  const isAudio = media.contentType.startsWith("audio/");
  const isVideo = media.contentType.startsWith("video/");
  const proxyUrl = `/api/whatsapp/media/${media.id}`;

  if (isImage) {
    return (
      <a href={proxyUrl} target="_blank" rel="noopener noreferrer">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={proxyUrl} alt="WhatsApp image" className="max-h-64 rounded-lg" loading="lazy" />
      </a>
    );
  }
  if (isAudio) {
    return (
      <audio controls preload="none" className="max-w-full">
        <source src={proxyUrl} type={media.contentType} />
      </audio>
    );
  }
  if (isVideo) {
    return (
      <video controls preload="none" className="max-h-64 max-w-full rounded-lg">
        <source src={proxyUrl} type={media.contentType} />
      </video>
    );
  }
  return (
    <a
      href={proxyUrl}
      target="_blank"
      rel="noopener noreferrer"
      className={cn(
        "flex items-center gap-2 rounded-md border px-3 py-2 text-xs hover:bg-muted/50 transition-colors",
        outbound ? "border-background/30" : "border-border"
      )}
    >
      <span>📎</span>
      <span className="truncate font-mono">
        {media.localPath ? media.localPath.split("/").pop() : media.contentType}
      </span>
      <span className="ml-auto shrink-0 text-[10px] opacity-60">Download</span>
    </a>
  );
}

function StatusDot({ status }: { status: string }) {
  const symbols: Record<string, string> = {
    queued: "○", sent: "✓", delivered: "✓✓", read: "✓✓", failed: "✗", undelivered: "✗", received: "✓",
  };
  return <span title={status}>{symbols[status] ?? status}</span>;
}
