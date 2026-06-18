"use client";

import { useTransition, useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import type { TranscribeResult } from "@/app/calls/actions";

type Props = {
  callId: number;
  hasRecording: boolean;
  hasTranscript: boolean;
  initialStatus: string;
  onTranscribe: () => Promise<TranscribeResult>;
};

function friendlyError(raw: string): string {
  if (raw.includes("fetch failed") || raw.includes("ECONNREFUSED") || raw.includes("ENOTFOUND")) {
    return "Transcriber service is unreachable. Make sure it's running (docker compose up transcriber).";
  }
  if (raw.includes("timed out") || raw.includes("AbortError")) {
    return "Transcription timed out. The audio may be too long or the service is overloaded.";
  }
  if (raw.includes("Twilio credentials")) {
    return "Twilio credentials not configured — cannot download recording.";
  }
  return raw;
}

export function TranscribeButton({ callId, hasRecording, hasTranscript, initialStatus, onTranscribe }: Props) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [polling, setPolling] = useState(initialStatus === "transcribing");
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setPolling(false);
  }, []);

  const startPolling = useCallback(() => {
    setPolling(true);
    intervalRef.current = setInterval(async () => {
      try {
        const res = await fetch(`/api/calls/${callId}/status`);
        if (!res.ok) return;
        const data = await res.json();

        if (data.hasTranscript) {
          stopPolling();
          toast.success("Transcription complete");
          router.refresh();
        } else if (data.status === "recorded" && data.errorMessage) {
          stopPolling();
          const msg = friendlyError(data.errorMessage);
          setError(msg);
          toast.error("Transcription failed", { description: msg });
        }
      } catch {}
    }, 3000);
  }, [callId, router, stopPolling]);

  useEffect(() => {
    if (initialStatus === "transcribing") startPolling();
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [initialStatus, startPolling]);

  if (!hasRecording) return null;
  if (hasTranscript) return null;

  const isWorking = isPending || polling;

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button
        variant="outline"
        disabled={isWorking}
        onClick={() => {
          setError(null);
          startTransition(async () => {
            try {
              const res = await onTranscribe();
              if ("error" in res) {
                const msg = friendlyError(res.error);
                setError(msg);
                toast.error("Transcription failed", { description: msg });
                return;
              }
              startPolling();
            } catch (err) {
              const raw = err instanceof Error ? err.message : String(err);
              const msg = friendlyError(raw);
              setError(msg);
              toast.error("Transcription failed", { description: msg });
            }
          });
        }}
      >
        {isWorking ? (
          <>
            <span className="mr-2 inline-block h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
            Transcribing…
          </>
        ) : error ? (
          "Retry transcription"
        ) : (
          "Transcribe"
        )}
      </Button>
      {isWorking && (
        <span className="text-xs text-muted-foreground">
          Sending audio to transcriber — this may take a minute
        </span>
      )}
      {error && (
        <p className="w-full text-xs text-destructive">{error}</p>
      )}
    </div>
  );
}
