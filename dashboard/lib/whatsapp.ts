import { prisma } from "@/lib/prisma";
import type { Prisma } from "@prisma/client";

export type ConversationRow = {
  id: number;
  contactPhone: string;
  contactName: string | null;
  lastMessageAt: Date;
  messageCount: number;
  lastBody: string | null;
  lastDirection: string | null;
  lastType: string | null;
};

export async function listConversations(): Promise<ConversationRow[]> {
  const convs = await prisma.whatsAppConversation.findMany({
    orderBy: { lastMessageAt: "desc" },
    take: 200,
    include: {
      messages: {
        orderBy: { createdAt: "desc" },
        take: 1,
        select: { body: true, direction: true, messageType: true },
      },
      _count: { select: { messages: true } },
    },
  });

  type Row = (typeof convs)[number];
  return convs.map((c: Row) => ({
    id: c.id,
    contactPhone: c.contactPhone,
    contactName: c.contactName,
    lastMessageAt: c.lastMessageAt,
    messageCount: c._count.messages,
    lastBody: c.messages[0]?.body ?? null,
    lastDirection: c.messages[0]?.direction ?? null,
    lastType: c.messages[0]?.messageType ?? null,
  }));
}

export type ThreadMessage = {
  id: number;
  twilioSid: string | null;
  direction: string;
  status: string;
  messageType: string;
  body: string | null;
  createdAt: Date;
  incidentFormId: number | null;
  media: {
    id: number;
    mediaIndex: number;
    contentType: string;
    localPath: string | null;
    twilioUrl: string;
  }[];
};

export type ConversationDetail = {
  id: number;
  contactPhone: string;
  contactName: string | null;
  createdAt: Date;
  messages: ThreadMessage[];
};

export async function getConversation(id: number): Promise<ConversationDetail | null> {
  const conv = await prisma.whatsAppConversation.findUnique({
    where: { id },
    include: {
      messages: {
        orderBy: { createdAt: "asc" },
        include: {
          media: {
            orderBy: { mediaIndex: "asc" },
            select: { id: true, mediaIndex: true, contentType: true, localPath: true, twilioUrl: true },
          },
        },
      },
    },
  });
  return conv;
}
