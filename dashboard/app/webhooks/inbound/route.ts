import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

function inferMessageType(numMedia: number, form: Record<string, string>): string {
  if (numMedia === 0) return "text";
  const ct = form["MediaContentType0"] ?? "";
  if (ct.startsWith("audio/")) return "voice_note";
  if (ct.startsWith("image/")) return "image";
  if (ct.startsWith("video/")) return "video";
  return "document";
}

export async function POST(req: NextRequest) {
  const formData = await req.formData();
  const form: Record<string, string> = {};
  formData.forEach((v, k) => {
    form[k] = String(v);
  });

  const messageSid = form["MessageSid"] ?? null;
  const from = form["From"] ?? "";
  const body = (form["Body"] ?? "").trim();
  const contactPhone = from.replace("whatsapp:", "");
  const contactName = form["ProfileName"] || null;
  const numMedia = parseInt(form["NumMedia"] ?? "0", 10);
  const messageType = inferMessageType(numMedia, form);

  const conversation = await prisma.whatsAppConversation.upsert({
    where: { contactPhone },
    update: { lastMessageAt: new Date(), contactName: contactName ?? undefined },
    create: { contactPhone, contactName, lastMessageAt: new Date() },
  });

  const message = await prisma.whatsAppMessage.create({
    data: {
      conversationId: conversation.id,
      twilioSid: messageSid,
      direction: "inbound",
      status: "received",
      messageType,
      body: body || null,
      rawPayload: form,
    },
  });

  for (let i = 0; i < numMedia; i++) {
    const mediaUrl = form[`MediaUrl${i}`];
    const contentType = form[`MediaContentType${i}`] ?? "application/octet-stream";
    if (!mediaUrl) continue;
    await prisma.whatsAppMedia.create({
      data: {
        messageId: message.id,
        mediaIndex: i,
        twilioUrl: mediaUrl,
        contentType,
      },
    });
  }

  const ack = messageType === "voice_note"
    ? "Got your voice note — transcribing now."
    : "Got it — processing your message.";

  const twiml = `<?xml version="1.0" encoding="UTF-8"?><Response><Message>${ack}</Message></Response>`;
  return new NextResponse(twiml, {
    status: 200,
    headers: { "Content-Type": "application/xml" },
  });
}
