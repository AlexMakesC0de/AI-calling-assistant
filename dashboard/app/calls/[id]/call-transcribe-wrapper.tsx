"use client";

import { TranscribeButton } from "@/components/transcribe-button";
import { transcribeCallAction } from "../actions";

export function CallTranscribeWrapper({
  callId,
  hasRecording,
  hasTranscript,
  initialStatus,
}: {
  callId: number;
  hasRecording: boolean;
  hasTranscript: boolean;
  initialStatus: string;
}) {
  return (
    <TranscribeButton
      callId={callId}
      hasRecording={hasRecording}
      hasTranscript={hasTranscript}
      initialStatus={initialStatus}
      onTranscribe={() => transcribeCallAction(callId)}
    />
  );
}
