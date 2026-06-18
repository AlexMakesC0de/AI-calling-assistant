"use server";

import { after } from "next/server";
import { revalidatePath } from "next/cache";
import { getSession } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import {
  getExistingAnalysis,
  markPending,
  runPipeline,
} from "@/lib/analyze-content";
import type { StartAnalysisResult } from "@/app/inbox/outlook/actions";

export async function analyzeCallAction(
  callId: number,
): Promise<StartAnalysisResult> {
  const session = await getSession();
  if (!session) return { started: false, error: "Not authenticated." };

  const sourceType = "twilio_call" as const;
  const sourceId = String(callId);

  const existing = await getExistingAnalysis(sourceType, sourceId);
  if (existing?.pipeline_status === "completed") {
    return { started: false, alreadyCompleted: true, sourceType, sourceId };
  }

  const call = await prisma.twilioCall.findUnique({
    where: { id: callId },
    include: { conversation: { select: { contactPhone: true, contactName: true, id: true } } },
  });

  if (!call) return { started: false, error: "Call not found." };
  if (!call.transcriptText?.trim()) return { started: false, error: "Call has no transcript text." };

  const sender = call.conversation?.contactName || call.conversation?.contactPhone || call.fromNumber || "Unknown";
  const subject = `Phone call from ${sender}`;
  const preview = call.transcriptText.slice(0, 200);
  const conversationId = call.conversation?.id;

  await markPending({ sourceType, sourceId, accountId: session.accountId, sender, contentPreview: preview });

  after(async () => {
    await runPipeline({
      sourceType,
      sourceId,
      subject,
      sender,
      body: call.transcriptText!,
      receivedAt: call.createdAt.toISOString(),
    });

    const updated = await prisma.$queryRaw<{ incident_form_id: number | null }[]>`
      SELECT incident_form_id FROM content_analysis
      WHERE source_type = ${sourceType} AND source_id = ${sourceId} LIMIT 1
    `.catch(() => []);

    if (updated[0]?.incident_form_id) {
      await prisma.twilioCall.update({
        where: { id: callId },
        data: { incidentFormId: updated[0].incident_form_id },
      }).catch(() => {});
      if (conversationId) revalidatePath(`/calls/${conversationId}`);
      revalidatePath("/incidents");
    }
  });

  return { started: true, sourceType, sourceId };
}
