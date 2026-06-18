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
import { fetchRecordingMp3 } from "@/lib/calls";
import { transcribeAudio } from "@/lib/transcriber";
import type { StartAnalysisResult } from "@/app/inbox/outlook/actions";

export type TranscribeResult =
  | { started: true; callId: number }
  | { started: false; error: string };

export async function transcribeCallAction(
  callId: number,
): Promise<TranscribeResult> {
  const session = await getSession();
  if (!session) return { started: false, error: "Not authenticated." };

  const call = await prisma.twilioCall.findUnique({
    where: { id: callId },
    include: { conversation: { select: { id: true } } },
  });

  if (!call) return { started: false, error: "Call not found." };
  if (!call.recordingTwilioUrl) return { started: false, error: "No recording available." };

  await prisma.twilioCall.update({
    where: { id: callId },
    data: { status: "transcribing", errorMessage: null },
  });

  const conversationId = call.conversation?.id;

  after(async () => {
    try {
      const mp3 = await fetchRecordingMp3(call.recordingTwilioUrl!);
      const filename = `${call.callSid}_${call.recordingSid || call.id}.mp3`;

      const result = await transcribeAudio({
        filename,
        bytes: mp3,
        contentType: "audio/mpeg",
      });

      await prisma.twilioCall.update({
        where: { id: callId },
        data: {
          status: "transcribed",
          transcriptText: result.text,
          errorMessage: null,
        },
      });

      if (conversationId) revalidatePath(`/calls/${conversationId}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error(`[transcribe] Call ${callId} failed:`, msg);
      await prisma.twilioCall
        .update({
          where: { id: callId },
          data: { status: "recorded", errorMessage: `Transcription failed: ${msg}` },
        })
        .catch(() => {});
      if (conversationId) revalidatePath(`/calls/${conversationId}`);
    }
  });

  return { started: true, callId };
}

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
