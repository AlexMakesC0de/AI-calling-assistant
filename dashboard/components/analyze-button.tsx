"use client";

import { useTransition, useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import type { SourceType } from "@/lib/analyze-content";

type ExistingAnalysis = {
  label: string;
  confidence: number;
  reason: string;
  incidentFormId: number | null;
  pipelineStatus: string;
  errorMessage: string | null;
};

type StartResult =
  | { started: true; sourceType: SourceType; sourceId: string }
  | { started: false; alreadyCompleted: true; sourceType: SourceType; sourceId: string }
  | { started: false; error: string };

type PollResult = {
  pipelineStatus: string;
  pipelineStep: string | null;
  classificationLabel: string | null;
  classificationConfidence: number | null;
  classificationReason: string | null;
  incidentFormId: number | null;
  errorMessage: string | null;
};

function stepLabel(step: string | null): string {
  switch (step) {
    case "classifying": return "Classifying…";
    case "saving": return "Creating incident…";
    default: return "Processing…";
  }
}

type Props = {
  existingAnalysis: ExistingAnalysis | null;
  onAnalyze: () => Promise<StartResult>;
  compact?: boolean;
};

function labelColor(label: string) {
  switch (label) {
    case "support": return "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400";
    case "not_support": return "bg-zinc-100 text-zinc-600 dark:bg-zinc-800/50 dark:text-zinc-400";
    case "unclear": return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400";
    default: return "bg-zinc-100 text-zinc-600";
  }
}

function friendlyError(raw: string): string {
  if (raw.includes("fetch failed") || raw.includes("ECONNREFUSED") || raw.includes("ENOTFOUND")) {
    return "AI analysis service is unreachable. Make sure voice-app is running (docker ps).";
  }
  if (raw.includes("timed out") || raw.includes("AbortError")) {
    return "Analysis timed out — the AI service took too long. Try again or check Ollama status.";
  }
  if (raw.includes("expired") || raw.includes("reconnect")) {
    return raw;
  }
  if (raw.includes("No text content") || raw.includes("body or subject is required")) {
    return "Nothing to analyze — this message has no text content.";
  }
  return raw;
}

function ClassificationDisplay({ label, confidence, reason, incidentId }: {
  label: string; confidence: number; reason: string; incidentId: number | null;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${labelColor(label)}`}>
        {label.replace("_", " ")}
      </span>
      <span className="text-xs text-muted-foreground">
        {Math.round(confidence * 100)}% confidence
      </span>
      {reason && (
        <span className="text-xs text-muted-foreground">— {reason}</span>
      )}
      {incidentId && (
        <Link
          href={`/incidents/${incidentId}`}
          className="text-xs underline underline-offset-4 hover:text-foreground"
        >
          View incident #{incidentId}
        </Link>
      )}
    </div>
  );
}

export function AnalyzeButton({ existingAnalysis, onAnalyze, compact }: Props) {
  const [isPending, startTransition] = useTransition();
  const [polling, setPolling] = useState(false);
  const [currentStep, setCurrentStep] = useState<string | null>(null);
  const [completed, setCompleted] = useState<PollResult | null>(null);
  const [error, setError] = useState<string | null>(
    existingAnalysis?.pipelineStatus === "failed" ? existingAnalysis.errorMessage : null,
  );
  const cleanupRef = useRef<(() => void) | null>(null);

  const stopListening = useCallback(() => {
    if (cleanupRef.current) {
      cleanupRef.current();
      cleanupRef.current = null;
    }
    setPolling(false);
  }, []);

  useEffect(() => {
    return () => { if (cleanupRef.current) cleanupRef.current(); };
  }, []);

  const handleResult = useCallback((data: PollResult) => {
    setCurrentStep(data.pipelineStep ?? null);

    if (data.pipelineStatus === "completed") {
      stopListening();
      setCompleted(data);
      const label = data.classificationLabel ?? "unknown";
      if (data.incidentFormId) {
        toast.success(`Classified as "${label}" — incident #${data.incidentFormId} created`);
      } else if (label === "not_support") {
        toast.info(`Classified as "not support" — no incident created`);
      } else {
        toast.success(`Classified as "${label}"`);
      }
    } else if (data.pipelineStatus === "failed") {
      stopListening();
      const msg = friendlyError(data.errorMessage ?? "Unknown error");
      setError(msg);
      toast.error("Analysis failed", { description: msg });
    }
  }, [stopListening]);

  const startFallbackPolling = useCallback((sourceType: SourceType, sourceId: string) => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/analysis/status?sourceType=${sourceType}&sourceId=${encodeURIComponent(sourceId)}`);
        if (!res.ok) return;
        const data = await res.json() as PollResult;
        handleResult(data);
      } catch {
        // keep trying
      }
    }, 4000);
    cleanupRef.current = () => clearInterval(interval);
  }, [handleResult]);

  const startPolling = useCallback((sourceType: SourceType, sourceId: string) => {
    setPolling(true);

    try {
      const es = new EventSource(`/api/analysis/stream?sourceType=${sourceType}&sourceId=${encodeURIComponent(sourceId)}`);

      es.addEventListener("status", (e) => {
        try {
          const data = JSON.parse(e.data) as PollResult;
          handleResult(data);
        } catch {}
      });

      es.onerror = () => {
        es.close();
        startFallbackPolling(sourceType, sourceId);
      };

      cleanupRef.current = () => es.close();
    } catch {
      startFallbackPolling(sourceType, sourceId);
    }
  }, [handleResult, startFallbackPolling]);

  // Already completed from server
  if (existingAnalysis?.pipelineStatus === "completed" && !completed) {
    return (
      <ClassificationDisplay
        label={existingAnalysis.label}
        confidence={existingAnalysis.confidence}
        reason={existingAnalysis.reason}
        incidentId={existingAnalysis.incidentFormId}
      />
    );
  }

  // Completed via polling
  if (completed) {
    return (
      <ClassificationDisplay
        label={completed.classificationLabel ?? "unknown"}
        confidence={completed.classificationConfidence ?? 0}
        reason={completed.classificationReason ?? ""}
        incidentId={completed.incidentFormId}
      />
    );
  }

  const isWorking = isPending || polling;

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button
        variant="outline"
        size={compact ? "sm" : "default"}
        disabled={isWorking}
        onClick={() => {
          setError(null);
          startTransition(async () => {
            try {
              const res = await onAnalyze();
              if ("error" in res) {
                const msg = friendlyError(res.error);
                setError(msg);
                toast.error("Analysis failed", { description: msg });
                return;
              }
              // started or alreadyCompleted — poll for result
              startPolling(res.sourceType, res.sourceId);
            } catch (err) {
              const raw = err instanceof Error ? err.message : String(err);
              const msg = friendlyError(raw);
              setError(msg);
              toast.error("Analysis failed", { description: msg });
            }
          });
        }}
      >
        {isWorking ? (
          <>
            <span className="mr-2 inline-block h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
            {polling ? stepLabel(currentStep) : "Starting…"}
          </>
        ) : error ? (
          "Retry analysis"
        ) : (
          "Analyze with AI"
        )}
      </Button>
      {isWorking && (
        <span className="text-xs text-muted-foreground">AI is analyzing in the background — you can navigate away</span>
      )}
      {error && (
        <p className="w-full text-xs text-destructive">{friendlyError(error)}</p>
      )}
    </div>
  );
}

export function AnalysisBadge({ label, incidentFormId }: { label: string; incidentFormId: number | null }) {
  return (
    <span className={`inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-medium ${labelColor(label)}`}>
      {label === "support" && incidentFormId ? `#${incidentFormId}` : label.replace("_", " ")}
    </span>
  );
}
