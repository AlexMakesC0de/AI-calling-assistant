import { NextRequest, NextResponse } from "next/server";
import { createHmac, timingSafeEqual } from "crypto";
import { mkdir, writeFile } from "fs/promises";
import { join } from "path";
import { prisma } from "@/lib/prisma";
import { env } from "@/lib/env";
import { guessExtension } from "@/lib/media-storage";

function validateTwilioSignature(
  authToken: string,
  url: string,
  params: Record<string, string>,
  signature: string,
): boolean {
  let data = url;
  for (const key of Object.keys(params).sort()) {
    data += key + params[key];
  }
  const expected = createHmac("sha1", authToken).update(data).digest("base64");
  try {
    return timingSafeEqual(Buffer.from(expected), Buffer.from(signature));
  } catch {
    return false;
  }
}

function inferMessageType(numMedia: number, form: Record<string, string>): string {
  if (numMedia === 0) return "text";
  const ct = form["MediaContentType0"] ?? "";
  if (ct.startsWith("audio/")) return "voice_note";
  if (ct.startsWith("image/")) return "image";
  if (ct.startsWith("video/")) return "video";
  return "document";
}

export async function POST(req: NextRequest) {
  const authToken = process.env.TWILIO_AUTH_TOKEN;
  if (authToken) {
    const signature = req.headers.get("x-twilio-signature") ?? "";
    const url = req.url;
    const formClone = await req.clone().formData();
    const params: Record<string, string> = {};
    formClone.forEach((v, k) => { params[k] = String(v); });
    if (!validateTwilioSignature(authToken, url, params, signature)) {
      return new NextResponse("Forbidden", { status: 403 });
    }
  }

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
    const mediaRecord = await prisma.whatsAppMedia.create({
      data: {
        messageId: message.id,
        mediaIndex: i,
        twilioUrl: mediaUrl,
        contentType,
      },
    });

    try {
      const sid = process.env.TWILIO_ACCOUNT_SID;
      const token = process.env.TWILIO_AUTH_TOKEN;
      if (sid && token) {
        const auth = "Basic " + Buffer.from(`${sid}:${token}`).toString("base64");
        const initial = await fetch(mediaUrl, {
          headers: { Authorization: auth },
          redirect: "manual",
        });
        let res: Response;
        const location = initial.headers.get("location");
        if (initial.status >= 300 && initial.status < 400 && location) {
          res = await fetch(location);
        } else {
          res = initial;
        }
        if (res.ok) {
          const ext = guessExtension(contentType);
          const filename = `${messageSid || message.id}_${i}${ext}`;
          await mkdir(env.whatsappMediaDir, { recursive: true });
          const localPath = join(env.whatsappMediaDir, filename);
          const buffer = Buffer.from(await res.arrayBuffer());
          await writeFile(localPath, buffer);
          await prisma.whatsAppMedia.update({
            where: { id: mediaRecord.id },
            data: { localPath, fileSizeBytes: buffer.length },
          });
        }
      }
    } catch (err) {
      console.error("Failed to download WhatsApp media locally:", err);
    }
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
