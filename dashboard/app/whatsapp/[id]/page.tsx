import { notFound } from "next/navigation";
import { getConversation } from "@/lib/whatsapp";
import { getAnalysisMap } from "@/lib/analyze-content";
import { WhatsAppThread } from "./whatsapp-thread";

export const dynamic = "force-dynamic";

export default async function WhatsAppThreadPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const numericId = Number(id);
  if (!Number.isFinite(numericId)) notFound();

  const conv = await getConversation(numericId);
  if (!conv) notFound();

  const textMsgIds = conv.messages
    .filter((m) => m.messageType === "text" && m.body?.trim() && m.direction === "inbound")
    .map((m) => String(m.id));
  const waAnalysisMap = await getAnalysisMap("whatsapp_text", textMsgIds);

  const serializedMessages = conv.messages.map((msg) => ({
    id: msg.id,
    direction: msg.direction,
    messageType: msg.messageType,
    body: msg.body,
    status: msg.status,
    createdAt: msg.createdAt instanceof Date ? msg.createdAt.toISOString() : String(msg.createdAt),
    incidentFormId: msg.incidentFormId,
    media: msg.media.map((m) => ({
      id: m.id,
      contentType: m.contentType,
      localPath: m.localPath,
    })),
  }));

  const analysisRecord: Record<string, { label: string; incidentFormId: number | null }> = {};
  for (const [key, value] of waAnalysisMap) {
    analysisRecord[key] = value;
  }

  return (
    <WhatsAppThread
      messages={serializedMessages}
      analysisMap={analysisRecord}
      contactPhone={conv.contactPhone}
      contactName={conv.contactName}
    />
  );
}
