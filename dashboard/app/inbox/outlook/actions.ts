"use server";

import { after } from "next/server";
import { revalidatePath } from "next/cache";
import { mkdir, writeFile } from "fs/promises";
import { join } from "path";
import { getSession } from "@/lib/auth";
import { getValidAccessToken } from "@/lib/outlook-oauth";
import { getValidGmailToken } from "@/lib/gmail-oauth";
import { prisma } from "@/lib/prisma";
import { env } from "@/lib/env";
import {
  getExistingAnalysis,
  markPending,
  runPipeline,
  type SourceType,
} from "@/lib/analyze-content";

type OutlookMessageFull = {
  subject?: string;
  from?: { emailAddress?: { address?: string } };
  body?: { content?: string; contentType?: string };
  receivedDateTime?: string;
};

type GmailHeader = { name: string; value: string };
type GmailPart = {
  mimeType: string;
  body?: { data?: string };
  parts?: GmailPart[];
};
type GmailFullMessage = {
  internalDate: string;
  payload: GmailPart & { headers: GmailHeader[] };
};

function getHeader(headers: GmailHeader[], name: string): string {
  return headers.find((h) => h.name.toLowerCase() === name.toLowerCase())?.value ?? "";
}

function extractPlainText(part: GmailPart): string | null {
  if (part.mimeType === "text/plain" && part.body?.data) {
    return Buffer.from(part.body.data, "base64url").toString("utf-8");
  }
  if (part.parts) {
    for (const sub of part.parts) {
      const result = extractPlainText(sub);
      if (result) return result;
    }
  }
  return null;
}

function stripHtml(html: string): string {
  return html
    .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, "")
    .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, "")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/\s+/g, " ")
    .trim();
}

export type StartAnalysisResult =
  | { started: true; sourceType: SourceType; sourceId: string }
  | { started: false; alreadyCompleted: true; sourceType: SourceType; sourceId: string }
  | { started: false; error: string };

export async function analyzeEmailAction(
  messageId: string,
  provider: "microsoft" | "google",
): Promise<StartAnalysisResult> {
  const session = await getSession();
  if (!session) return { started: false, error: "Not authenticated." };

  const sourceType: SourceType = provider === "microsoft" ? "outlook_email" : "gmail_email";

  const existing = await getExistingAnalysis(sourceType, messageId);
  if (existing?.pipeline_status === "completed") {
    return { started: false, alreadyCompleted: true, sourceType, sourceId: messageId };
  }

  let subject = "";
  let sender = "";
  let body = "";
  let receivedAt = "";

  try {
    if (provider === "microsoft") {
      const creds = await getValidAccessToken(session.accountId);
      if (!creds) return { started: false, error: "Microsoft connection expired. Please reconnect." };

      const res = await fetch(
        `https://graph.microsoft.com/v1.0/me/messages/${encodeURIComponent(messageId)}?$select=subject,from,body,receivedDateTime`,
        { headers: { Authorization: `Bearer ${creds.token}`, Accept: "application/json" }, cache: "no-store" },
      );
      if (!res.ok) return { started: false, error: `Failed to fetch email (${res.status})` };
      const msg = (await res.json()) as OutlookMessageFull;

      subject = msg.subject ?? "";
      sender = msg.from?.emailAddress?.address ?? "";
      receivedAt = msg.receivedDateTime ?? "";
      const rawBody = msg.body?.content ?? "";
      body = msg.body?.contentType === "html" ? stripHtml(rawBody) : rawBody;
    } else {
      const creds = await getValidGmailToken(session.accountId);
      if (!creds) return { started: false, error: "Gmail connection expired. Please reconnect." };

      const res = await fetch(
        `https://gmail.googleapis.com/gmail/v1/users/me/messages/${encodeURIComponent(messageId)}?format=full`,
        { headers: { Authorization: `Bearer ${creds.token}` }, cache: "no-store" },
      );
      if (!res.ok) return { started: false, error: `Failed to fetch email (${res.status})` };
      const msg = (await res.json()) as GmailFullMessage;

      subject = getHeader(msg.payload.headers, "Subject");
      const fromRaw = getHeader(msg.payload.headers, "From");
      const fromMatch = fromRaw.match(/<(.+?)>/);
      sender = fromMatch ? fromMatch[1] : fromRaw;
      receivedAt = new Date(Number(msg.internalDate)).toISOString();
      body = extractPlainText(msg.payload) ?? "";
    }
  } catch (err) {
    return { started: false, error: `Failed to fetch email: ${err instanceof Error ? err.message : String(err)}` };
  }

  const preview = (subject || body).slice(0, 200);
  await markPending({ sourceType, sourceId: messageId, accountId: session.accountId, sender, contentPreview: preview });

  after(async () => {
    await runPipeline({ sourceType, sourceId: messageId, subject, sender, body, receivedAt });

    const updated = await prisma.$queryRaw<{ incident_form_id: number | null }[]>`
      SELECT incident_form_id FROM content_analysis
      WHERE source_type = ${sourceType} AND source_id = ${messageId} LIMIT 1
    `.catch(() => []);
    if (updated[0]?.incident_form_id) {
      revalidatePath("/inbox/outlook");
      revalidatePath("/incidents");
    }
  });

  return { started: true, sourceType, sourceId: messageId };
}

export type SaveEmailResult =
  | { saved: true; emailMessageId: number }
  | { saved: false; alreadySaved: true; emailMessageId: number }
  | { saved: false; error: string };

type OutlookAttachmentDetail = {
  id: string;
  name: string;
  contentType: string;
  size: number;
  contentBytes?: string;
  isInline?: boolean;
  contentId?: string;
};

type GmailAttachmentInfo = { attachmentId: string; name: string; contentType: string; size: number };
type GmailPartForSave = {
  mimeType: string;
  filename?: string;
  body?: { data?: string; size?: number; attachmentId?: string };
  parts?: GmailPartForSave[];
  headers?: GmailHeader[];
};

function collectGmailAttachments(part: GmailPartForSave): GmailAttachmentInfo[] {
  const result: GmailAttachmentInfo[] = [];
  if (part.filename && part.body?.attachmentId) {
    result.push({ attachmentId: part.body.attachmentId, name: part.filename, contentType: part.mimeType, size: part.body.size ?? 0 });
  }
  if (part.parts) {
    for (const sub of part.parts) result.push(...collectGmailAttachments(sub));
  }
  return result;
}

function extractHtmlBody(part: GmailPartForSave): string | null {
  if (part.mimeType === "text/html" && part.body?.data) {
    return Buffer.from(part.body.data, "base64url").toString("utf-8");
  }
  if (part.parts) {
    for (const sub of part.parts) {
      const r = extractHtmlBody(sub);
      if (r) return r;
    }
  }
  return null;
}

export async function saveEmailToDbAction(
  messageId: string,
  provider: "microsoft" | "google",
): Promise<SaveEmailResult> {
  const session = await getSession();
  if (!session) return { saved: false, error: "Not authenticated." };

  const existing = await prisma.emailMessage.findFirst({
    where: { messageIdHeader: messageId },
    select: { id: true },
  });
  if (existing) return { saved: false, alreadySaved: true, emailMessageId: existing.id };

  try {
    if (provider === "microsoft") {
      return await saveOutlookEmail(messageId, session.accountId);
    } else {
      return await saveGmailEmail(messageId, session.accountId);
    }
  } catch (err) {
    return { saved: false, error: `Failed to save: ${err instanceof Error ? err.message : String(err)}` };
  }
}

async function saveOutlookEmail(messageId: string, accountId: number): Promise<SaveEmailResult> {
  const creds = await getValidAccessToken(accountId);
  if (!creds) return { saved: false, error: "Microsoft connection expired. Please reconnect." };

  const msgRes = await fetch(
    `https://graph.microsoft.com/v1.0/me/messages/${encodeURIComponent(messageId)}?$select=subject,from,toRecipients,ccRecipients,body,receivedDateTime,internetMessageId,hasAttachments,isRead`,
    { headers: { Authorization: `Bearer ${creds.token}`, Accept: "application/json" }, cache: "no-store" },
  );
  if (!msgRes.ok) return { saved: false, error: `Failed to fetch email (${msgRes.status})` };

  const msg = await msgRes.json();
  const senderEmail = msg.from?.emailAddress?.address ?? "unknown";
  const senderName = msg.from?.emailAddress?.name ?? null;
  const toAddresses = (msg.toRecipients ?? []).map((r: { emailAddress?: { address?: string } }) => r.emailAddress?.address).filter(Boolean).join(", ");
  const ccAddresses = (msg.ccRecipients ?? []).map((r: { emailAddress?: { address?: string } }) => r.emailAddress?.address).filter(Boolean).join(", ");
  const isHtml = msg.body?.contentType === "html";
  const bodyText = isHtml ? stripHtml(msg.body?.content ?? "") : (msg.body?.content ?? "");
  const bodyHtml = isHtml ? (msg.body?.content ?? null) : null;

  const conversation = await prisma.emailConversation.upsert({
    where: { senderEmail },
    create: { senderEmail, senderName, lastMessageAt: new Date(msg.receivedDateTime ?? Date.now()) },
    update: { lastMessageAt: new Date(msg.receivedDateTime ?? Date.now()), ...(senderName ? { senderName } : {}) },
  });

  const emailMsg = await prisma.emailMessage.create({
    data: {
      conversationId: conversation.id,
      messageIdHeader: msg.internetMessageId ?? messageId,
      direction: "inbound",
      subject: msg.subject ?? null,
      fromEmail: senderEmail,
      fromName: senderName,
      toEmail: toAddresses || null,
      cc: ccAddresses || null,
      bodyText: bodyText || null,
      bodyHtml: bodyHtml,
    },
  });

  if (msg.hasAttachments) {
    try {
      const attRes = await fetch(
        `https://graph.microsoft.com/v1.0/me/messages/${encodeURIComponent(messageId)}/attachments`,
        { headers: { Authorization: `Bearer ${creds.token}`, Accept: "application/json" }, cache: "no-store" },
      );
      if (attRes.ok) {
        const attJson = await attRes.json();
        const attachments = (attJson.value ?? []) as OutlookAttachmentDetail[];
        const dir = join(env.outlookAttachmentsDir, messageId.replace(/[^a-zA-Z0-9-_]/g, "_"));
        await mkdir(dir, { recursive: true });

        for (let i = 0; i < attachments.length; i++) {
          const att = attachments[i];
          if (!att.contentBytes) continue;
          const safeName = (att.name ?? `attachment_${i}`).replace(/[/\\:*?"<>|]/g, "_");
          const filePath = join(dir, `${i}_${safeName}`);
          await writeFile(filePath, Buffer.from(att.contentBytes, "base64"));

          await prisma.emailAttachment.create({
            data: {
              messageId: emailMsg.id,
              attachmentIndex: i,
              externalId: att.id,
              fileName: att.name,
              contentType: att.contentType,
              localPath: filePath,
              fileSizeBytes: att.size,
              contentId: att.contentId ?? null,
            },
          });
        }
      }
    } catch {
      // attachments are best-effort
    }
  }

  revalidatePath("/inbox/outlook");
  return { saved: true, emailMessageId: emailMsg.id };
}

async function saveGmailEmail(messageId: string, accountId: number): Promise<SaveEmailResult> {
  const creds = await getValidGmailToken(accountId);
  if (!creds) return { saved: false, error: "Gmail connection expired. Please reconnect." };

  const msgRes = await fetch(
    `https://gmail.googleapis.com/gmail/v1/users/me/messages/${encodeURIComponent(messageId)}?format=full`,
    { headers: { Authorization: `Bearer ${creds.token}` }, cache: "no-store" },
  );
  if (!msgRes.ok) return { saved: false, error: `Failed to fetch email (${msgRes.status})` };

  const msg = await msgRes.json();
  const headers = msg.payload?.headers ?? [];
  const subject = getHeader(headers, "Subject");
  const fromRaw = getHeader(headers, "From");
  const fromMatch = fromRaw.match(/<(.+?)>/);
  const senderEmail = fromMatch ? fromMatch[1] : fromRaw || "unknown";
  const nameMatch = fromRaw.match(/^"?(.+?)"?\s+</);
  const senderName = nameMatch ? nameMatch[1] : null;
  const toEmail = getHeader(headers, "To") || null;
  const cc = getHeader(headers, "Cc") || null;
  const gmailMessageId = getHeader(headers, "Message-ID") || messageId;
  const receivedAt = new Date(Number(msg.internalDate));

  const bodyText = extractPlainText(msg.payload) ?? "";
  const bodyHtml = extractHtmlBody(msg.payload) ?? null;

  const conversation = await prisma.emailConversation.upsert({
    where: { senderEmail },
    create: { senderEmail, senderName, lastMessageAt: receivedAt },
    update: { lastMessageAt: receivedAt, ...(senderName ? { senderName } : {}) },
  });

  const emailMsg = await prisma.emailMessage.create({
    data: {
      conversationId: conversation.id,
      messageIdHeader: gmailMessageId,
      direction: "inbound",
      subject: subject || null,
      fromEmail: senderEmail,
      fromName: senderName,
      toEmail,
      cc,
      bodyText: bodyText || null,
      bodyHtml,
    },
  });

  const gmailAttachments = collectGmailAttachments(msg.payload);
  if (gmailAttachments.length > 0) {
    const dir = join(env.emailAttachmentsDir, messageId.replace(/[^a-zA-Z0-9-_]/g, "_"));
    await mkdir(dir, { recursive: true });

    for (let i = 0; i < gmailAttachments.length; i++) {
      const att = gmailAttachments[i];
      try {
        const attRes = await fetch(
          `https://gmail.googleapis.com/gmail/v1/users/me/messages/${encodeURIComponent(messageId)}/attachments/${encodeURIComponent(att.attachmentId)}`,
          { headers: { Authorization: `Bearer ${creds.token}` }, cache: "no-store" },
        );
        if (!attRes.ok) continue;
        const attJson = await attRes.json();
        if (!attJson.data) continue;

        const safeName = (att.name ?? `attachment_${i}`).replace(/[/\\:*?"<>|]/g, "_");
        const filePath = join(dir, `${i}_${safeName}`);
        await writeFile(filePath, Buffer.from(attJson.data, "base64url"));

        await prisma.emailAttachment.create({
          data: {
            messageId: emailMsg.id,
            attachmentIndex: i,
            externalId: att.attachmentId,
            fileName: att.name,
            contentType: att.contentType,
            localPath: filePath,
            fileSizeBytes: att.size,
          },
        });
      } catch {
        // best-effort per attachment
      }
    }
  }

  revalidatePath("/inbox/outlook");
  return { saved: true, emailMessageId: emailMsg.id };
}
