import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { env } from "@/lib/env";
import { mkdir, writeFile } from "fs/promises";
import { join } from "path";

function parseEmailAddress(raw: string): { email: string; name: string | null } {
  const match = raw.match(/^(?:"?(.+?)"?\s+)?<?([^\s>]+@[^\s>]+)>?$/);
  if (match) return { email: match[2].toLowerCase(), name: match[1]?.trim() || null };
  return { email: raw.trim().toLowerCase(), name: null };
}

export async function POST(req: NextRequest) {
  const formData = await req.formData();
  const fields: Record<string, string> = {};
  const files: Map<string, File> = new Map();

  for (const [key, value] of formData.entries()) {
    if (value instanceof File) {
      files.set(key, value);
    } else {
      fields[key] = String(value);
    }
  }

  const { email: senderEmail, name: senderName } = parseEmailAddress(fields["from"] ?? "");
  const subject = fields["subject"] ?? null;
  const bodyText = fields["text"] ?? null;
  const bodyHtml = fields["html"] ?? null;
  const toEmail = fields["to"] ?? null;
  const cc = fields["cc"] ?? null;
  const messageIdHeader = fields["Message-ID"] ?? null;

  let headersJson: Record<string, string> = {};
  try {
    const rawHeaders = fields["headers"] ?? "";
    if (rawHeaders) {
      const parsed: Record<string, string> = {};
      for (const line of rawHeaders.split(/\r?\n/)) {
        const idx = line.indexOf(":");
        if (idx > 0) parsed[line.slice(0, idx).trim()] = line.slice(idx + 1).trim();
      }
      headersJson = parsed;
    }
  } catch { /* keep empty */ }

  let envelopeJson = {};
  try { envelopeJson = JSON.parse(fields["envelope"] ?? "{}"); } catch { /* keep empty */ }

  const conversation = await prisma.emailConversation.upsert({
    where: { senderEmail },
    update: { lastMessageAt: new Date(), senderName: senderName ?? undefined },
    create: { senderEmail, senderName, lastMessageAt: new Date() },
  });

  const message = await prisma.emailMessage.create({
    data: {
      conversationId: conversation.id,
      messageIdHeader,
      direction: "inbound",
      subject,
      fromEmail: senderEmail,
      fromName: senderName,
      toEmail,
      cc,
      bodyText,
      bodyHtml,
      headers: headersJson,
      envelope: envelopeJson,
      rawPayload: fields,
    },
  });

  let attachmentInfoMap: Record<string, { filename?: string; type?: string; "content-id"?: string }> = {};
  try { attachmentInfoMap = JSON.parse(fields["attachment-info"] ?? "{}"); } catch { /* ignore */ }

  let attachmentIndex = 0;
  for (const [key, info] of Object.entries(attachmentInfoMap)) {
    const fileKey = `attachment${parseInt(key, 10) + 1}`;
    const file = files.get(fileKey) ?? files.get(key);
    if (!file) continue;

    const fileName = info.filename ?? file.name ?? `attachment_${attachmentIndex}`;
    const contentType = info.type ?? file.type ?? "application/octet-stream";
    const contentId = info["content-id"] ?? null;

    const dir = join(env.emailAttachmentsDir, String(message.id));
    await mkdir(dir, { recursive: true });
    const safeName = fileName.replace(/[^a-zA-Z0-9._-]/g, "_");
    const localPath = join(dir, `${attachmentIndex}_${safeName}`);

    const buffer = Buffer.from(await file.arrayBuffer());
    await writeFile(localPath, buffer);

    await prisma.emailAttachment.create({
      data: {
        messageId: message.id,
        attachmentIndex,
        fileName,
        contentType,
        localPath,
        fileSizeBytes: buffer.length,
        contentId,
      },
    });

    attachmentIndex++;
  }

  return new NextResponse(null, { status: 200 });
}
