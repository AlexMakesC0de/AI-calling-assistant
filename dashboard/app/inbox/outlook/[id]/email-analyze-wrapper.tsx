"use client";

import { AnalyzeButton } from "@/components/analyze-button";
import { analyzeEmailAction } from "../actions";

type ExistingAnalysis = {
  label: string;
  confidence: number;
  reason: string;
  incidentFormId: number | null;
  pipelineStatus: string;
  errorMessage: string | null;
};

export function EmailAnalyzeWrapper({
  messageId,
  provider,
  existingAnalysis,
}: {
  messageId: string;
  provider: "microsoft" | "google";
  existingAnalysis: ExistingAnalysis | null;
}) {
  return (
    <AnalyzeButton
      existingAnalysis={existingAnalysis}
      onAnalyze={() => analyzeEmailAction(messageId, provider)}
    />
  );
}
