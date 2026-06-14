"use server";

import { prisma } from "@/lib/prisma";
import { asFormData } from "@/lib/incident-form";

export type IncidentItem = {
  id: number;
  callerName: string | null;
  category: string | null;
  priority: string | null;
  summary: string | null;
  sentiment: string | null;
  completedAt: string;
};

export type WhatsAppItem = {
  id: number;
  contactPhone: string;
  contactName: string | null;
  messageCount: number;
  lastMessage: string | null;
  lastMessageAt: string;
};

export type EmailItem = {
  id: number;
  senderEmail: string;
  senderName: string | null;
  messageCount: number;
  lastSubject: string | null;
  lastMessageAt: string;
};

export async function loadSelectableItems() {
  const [incidents, whatsapp] = await Promise.all([
    prisma.incidentForm.findMany({
      include: {
        generalInformation: true,
        transcriptions: { where: { langCode: { not: "nl" } }, take: 1 },
      },
      orderBy: { completedAt: "desc" },
      take: 100,
    }),
    prisma.whatsAppConversation.findMany({
      orderBy: { lastMessageAt: "desc" },
      take: 100,
      include: {
        messages: { orderBy: { createdAt: "desc" }, take: 1, select: { body: true } },
        _count: { select: { messages: true } },
      },
    }),
  ]);

  // Email model isn't in the generated Prisma client yet (needs prisma generate).
  // Fall back to a raw query so the page still works.
  let emailItems: EmailItem[] = [];
  try {
    const rows = await prisma.$queryRaw<
      { id: number; sender_email: string; sender_name: string | null; last_message_at: Date; message_count: bigint; last_subject: string | null }[]
    >`
      SELECT c.id, c.sender_email, c.sender_name, c.last_message_at,
             (SELECT COUNT(*) FROM email_message m WHERE m.conversation_id = c.id) AS message_count,
             (SELECT m.subject FROM email_message m WHERE m.conversation_id = c.id ORDER BY m.created_at DESC LIMIT 1) AS last_subject
      FROM email_conversation c
      ORDER BY c.last_message_at DESC
      LIMIT 100
    `;
    emailItems = rows.map((r) => ({
      id: r.id,
      senderEmail: r.sender_email,
      senderName: r.sender_name,
      messageCount: Number(r.message_count),
      lastSubject: r.last_subject,
      lastMessageAt: r.last_message_at.toISOString(),
    }));
  } catch {
    // table may not exist yet — return empty
  }

  const incidentItems: IncidentItem[] = incidents.map((inc) => {
    const data = asFormData(inc.generalInformation?.formData);
    return {
      id: inc.id,
      callerName: inc.generalInformation?.callerName ?? null,
      category: inc.category,
      priority: inc.priority,
      summary: data.call_summary || inc.transcriptions[0]?.summary || null,
      sentiment: inc.transcriptions[0]?.sentiment ?? data.customer_sentiment ?? null,
      completedAt: inc.completedAt.toISOString(),
    };
  });

  const whatsappItems: WhatsAppItem[] = whatsapp.map((c) => ({
    id: c.id,
    contactPhone: c.contactPhone,
    contactName: c.contactName,
    messageCount: c._count.messages,
    lastMessage: c.messages[0]?.body ?? null,
    lastMessageAt: c.lastMessageAt.toISOString(),
  }));

  return { incidents: incidentItems, whatsapp: whatsappItems, email: emailItems };
}
