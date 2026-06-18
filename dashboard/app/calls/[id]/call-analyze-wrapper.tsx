"use client";

import { AnalyzeButton } from "@/components/analyze-button";
import { analyzeCallAction } from "../actions";

type ExistingAnalysis = {
  label: string;
  confidence: number;
  reason: string;
  incidentFormId: number | null;
  pipelineStatus: string;
  errorMessage: string | null;
};

export function CallAnalyzeWrapper({
  callId,
  existingAnalysis,
}: {
  callId: number;
  existingAnalysis: ExistingAnalysis | null;
}) {
  return (
    <AnalyzeButton
      existingAnalysis={existingAnalysis}
      onAnalyze={() => analyzeCallAction(callId)}
    />
  );
}
