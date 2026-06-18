import Link from "next/link";
import { notFound } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { getConversation, type CallDetail } from "@/lib/calls";
import { getAnalysisMap } from "@/lib/analyze-content";
import { formatDateTime } from "@/lib/utils";
import { CopyButton } from "@/components/copy-button";
import { CallAnalyzeWrapper } from "./call-analyze-wrapper";
import { CallTranscribeWrapper } from "./call-transcribe-wrapper";

export const dynamic = "force-dynamic";

function formatDuration(seconds: number | null): string {
  if (seconds == null) return "—";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function statusVariant(status: string): "default" | "solid" | "muted" {
  switch (status) {
    case "completed":
    case "transcribed":
      return "muted";
    case "failed":
      return "solid";
    default:
      return "default";
  }
}

export default async function CallConversationPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const numericId = Number(id);
  if (!Number.isFinite(numericId)) notFound();

  const conv = await getConversation(numericId);
  if (!conv) notFound();

  const callIds = conv.calls.map((c) => String(c.id));
  const analysisMap = await getAnalysisMap("twilio_call", callIds);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h1 className="text-2xl font-medium tracking-tight">
            {conv.contactName || conv.contactPhone}
          </h1>
          {conv.contactName && (
            <p className="flex items-center gap-1.5 font-mono text-xs text-muted-foreground">
              {conv.contactPhone} <CopyButton value={conv.contactPhone} />
            </p>
          )}
        </div>
        <Link href="/calls" className="text-sm text-muted-foreground hover:text-foreground">
          &larr; Back to calls
        </Link>
      </div>

      {conv.calls.length === 0 ? (
        <div className="rounded-md border border-border p-12 text-center text-sm text-muted-foreground">
          No calls in this conversation.
        </div>
      ) : (
        <div className="space-y-4">
          {conv.calls.map((call) => (
            <CallCard key={call.id} call={call} analysisMap={analysisMap} />
          ))}
        </div>
      )}
    </div>
  );
}

function CallCard({
  call,
  analysisMap,
}: {
  call: CallDetail;
  analysisMap: Map<string, { label: string; incidentFormId: number | null }>;
}) {
  const existing = analysisMap.get(String(call.id));
  const analysisProps = existing
    ? {
        label: existing.label,
        confidence: 0,
        reason: "",
        incidentFormId: existing.incidentFormId,
        pipelineStatus: "completed" as const,
        errorMessage: null,
      }
    : call.status === "failed"
      ? {
          label: "failed",
          confidence: 0,
          reason: call.errorMessage ?? "Pipeline failed",
          incidentFormId: null,
          pipelineStatus: "failed" as const,
          errorMessage: call.errorMessage,
        }
      : null;

  const hasRecording = Boolean(call.localRecordingPath || call.recordingTwilioUrl);
  const hasTranscript = Boolean(call.transcriptText);

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-medium">
            {call.direction === "inbound" ? "Inbound" : "Outbound"} call
          </CardTitle>
          <div className="flex items-center gap-2">
            <Badge variant={statusVariant(call.status)}>{call.status}</Badge>
            <span className="text-sm text-muted-foreground">{formatDateTime(call.createdAt)}</span>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Metadata */}
        <div className="grid grid-cols-2 gap-x-8 gap-y-1 text-sm sm:grid-cols-4">
          <div>
            <span className="text-muted-foreground">From</span>
            <p className="flex items-center gap-1.5 font-mono">
              {call.fromNumber || "—"}
              {call.fromNumber && <CopyButton value={call.fromNumber} />}
            </p>
          </div>
          <div>
            <span className="text-muted-foreground">To</span>
            <p className="flex items-center gap-1.5 font-mono">
              {call.toNumber || "—"}
              {call.toNumber && <CopyButton value={call.toNumber} />}
            </p>
          </div>
          <div>
            <span className="text-muted-foreground">Duration</span>
            <p className="tabular-nums">{formatDuration(call.durationSeconds)}</p>
          </div>
          <div>
            <span className="text-muted-foreground">Call SID</span>
            <p className="flex items-center gap-1.5 truncate font-mono text-xs">
              {call.callSid}
              {call.callSid && <CopyButton value={call.callSid} />}
            </p>
          </div>
        </div>

        {/* Audio player */}
        {hasRecording && (
          <>
            <Separator />
            <div>
              <p className="mb-2 text-sm font-medium">Recording</p>
              <audio controls preload="none" className="w-full">
                <source src={`/api/calls/recordings/${call.id}`} type="audio/mpeg" />
              </audio>
            </div>
          </>
        )}

        {/* Transcribe button */}
        {hasRecording && !hasTranscript && (
          <>
            <Separator />
            <CallTranscribeWrapper
              callId={call.id}
              hasRecording={hasRecording}
              hasTranscript={hasTranscript}
              initialStatus={call.status}
            />
          </>
        )}

        {/* Transcript */}
        {hasTranscript && (
          <>
            <Separator />
            <div>
              <p className="mb-2 text-sm font-medium">Transcript</p>
              <div className="max-h-64 overflow-y-auto rounded-md border border-border bg-muted/30 p-3">
                <p className="whitespace-pre-wrap text-sm leading-relaxed">{call.transcriptText}</p>
              </div>
            </div>
          </>
        )}

        {/* Incident link */}
        {call.incidentFormId && (
          <>
            <Separator />
            <div>
              <Link
                href={`/incidents/${call.incidentFormId}`}
                className="text-sm underline underline-offset-4 hover:text-foreground"
              >
                View incident #{call.incidentFormId} &rarr;
              </Link>
            </div>
          </>
        )}

        {/* Analysis / re-analyze button */}
        {hasTranscript && (
          <>
            <Separator />
            <CallAnalyzeWrapper callId={call.id} existingAnalysis={analysisProps} />
          </>
        )}

        {/* Error message */}
        {call.status === "failed" && call.errorMessage && (
          <p className="text-xs text-destructive">{call.errorMessage}</p>
        )}
      </CardContent>
    </Card>
  );
}
