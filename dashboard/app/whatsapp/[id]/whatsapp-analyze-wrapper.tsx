"use client";

import { AnalyzeButton } from "@/components/analyze-button";
import { analyzeWhatsAppAction } from "../actions";

type ExistingAnalysis = {
  label: string;
  confidence: number;
  reason: string;
  incidentFormId: number | null;
  pipelineStatus: string;
  errorMessage: string | null;
};

export function WhatsAppAnalyzeWrapper({
  messageId,
  existingAnalysis,
}: {
  messageId: number;
  existingAnalysis: ExistingAnalysis | null;
}) {
  return (
    <AnalyzeButton
      existingAnalysis={existingAnalysis}
      onAnalyze={() => analyzeWhatsAppAction(messageId)}
      compact
    />
  );
}
