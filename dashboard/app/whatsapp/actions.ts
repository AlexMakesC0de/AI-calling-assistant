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

export async function analyzeWhatsAppAction(
  messageId: number,
): Promise<StartAnalysisResult> {
  const session = await getSession();
  if (!session) return { started: false, error: "Not authenticated." };

  const sourceType = "whatsapp_text" as const;
  const sourceId = String(messageId);

  const existing = await getExistingAnalysis(sourceType, sourceId);
  if (existing?.pipeline_status === "completed") {
    return { started: false, alreadyCompleted: true, sourceType, sourceId };
  }

  const msg = await prisma.whatsAppMessage.findUnique({
    where: { id: messageId },
    include: { conversation: { select: { contactPhone: true, contactName: true, id: true } } },
  });

  if (!msg) return { started: false, error: "Message not found." };
  if (!msg.body?.trim()) return { started: false, error: "Message has no text content." };

  const sender = msg.conversation.contactName || msg.conversation.contactPhone;
  const subject = `WhatsApp message from ${sender}`;
  const preview = msg.body.slice(0, 200);
  const conversationId = msg.conversation.id;

  await markPending({ sourceType, sourceId, accountId: session.accountId, sender, contentPreview: preview });

  after(async () => {
    await runPipeline({
      sourceType,
      sourceId,
      subject,
      sender,
      body: msg.body!,
      receivedAt: msg.createdAt.toISOString(),
    });

    const updated = await prisma.$queryRaw<{ incident_form_id: number | null }[]>`
      SELECT incident_form_id FROM content_analysis
      WHERE source_type = ${sourceType} AND source_id = ${sourceId} LIMIT 1
    `.catch(() => []);

    if (updated[0]?.incident_form_id) {
      await prisma.whatsAppMessage.update({
        where: { id: messageId },
        data: { incidentFormId: updated[0].incident_form_id },
      }).catch(() => {});
      revalidatePath(`/whatsapp/${conversationId}`);
      revalidatePath("/incidents");
    }
  });

  return { started: true, sourceType, sourceId };
}

export type BatchAnalysisResult =
  | { started: true; sourceType: "whatsapp_text"; sourceIds: string[] }
  | { started: false; error: string };

export async function analyzeWhatsAppBatchAction(
  messageIds: number[],
): Promise<BatchAnalysisResult> {
  const session = await getSession();
  if (!session) return { started: false, error: "Not authenticated." };
  if (messageIds.length === 0) return { started: false, error: "No messages selected." };

  const sourceType = "whatsapp_text" as const;
  const messages = await prisma.whatsAppMessage.findMany({
    where: { id: { in: messageIds } },
    include: { conversation: { select: { contactPhone: true, contactName: true, id: true } } },
  });

  const validMessages = messages.filter((m) => m.body?.trim());
  if (validMessages.length === 0) return { started: false, error: "No messages have text content." };

  const sourceIds: string[] = [];

  for (const msg of validMessages) {
    const sourceId = String(msg.id);
    const existing = await getExistingAnalysis(sourceType, sourceId);
    if (existing?.pipeline_status === "completed") continue;

    const sender = msg.conversation.contactName || msg.conversation.contactPhone;
    const preview = msg.body!.slice(0, 200);
    await markPending({ sourceType, sourceId, accountId: session.accountId, sender, contentPreview: preview });
    sourceIds.push(sourceId);
  }

  if (sourceIds.length === 0) return { started: false, error: "All selected messages are already analyzed." };

  after(async () => {
    for (const msg of validMessages) {
      const sourceId = String(msg.id);
      if (!sourceIds.includes(sourceId)) continue;

      const sender = msg.conversation.contactName || msg.conversation.contactPhone;
      const subject = `WhatsApp message from ${sender}`;
      const conversationId = msg.conversation.id;

      await runPipeline({
        sourceType,
        sourceId,
        subject,
        sender,
        body: msg.body!,
        receivedAt: msg.createdAt.toISOString(),
      });

      const updated = await prisma.$queryRaw<{ incident_form_id: number | null }[]>`
        SELECT incident_form_id FROM content_analysis
        WHERE source_type = ${sourceType} AND source_id = ${sourceId} LIMIT 1
      `.catch(() => []);

      if (updated[0]?.incident_form_id) {
        await prisma.whatsAppMessage.update({
          where: { id: msg.id },
          data: { incidentFormId: updated[0].incident_form_id },
        }).catch(() => {});
        revalidatePath(`/whatsapp/${conversationId}`);
        revalidatePath("/incidents");
      }
    }
  });

  return { started: true, sourceType, sourceIds };
}
