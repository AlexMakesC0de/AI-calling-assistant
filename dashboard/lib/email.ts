import { prisma } from "@/lib/prisma";

export type EmailConversationRow = {
  id: number;
  senderEmail: string;
  senderName: string | null;
  lastMessageAt: Date;
  messageCount: number;
  lastSubject: string | null;
  lastSnippet: string | null;
};

export type EmailThreadMessage = {
  id: number;
  direction: string;
  subject: string | null;
  fromEmail: string;
  fromName: string | null;
  toEmail: string | null;
  cc: string | null;
  bodyText: string | null;
  bodyHtml: string | null;
  createdAt: Date;
  attachments: {
    id: number;
    attachmentIndex: number;
    fileName: string | null;
    contentType: string;
    fileSizeBytes: bigint | null;
  }[];
};

export type EmailConversationDetail = {
  id: number;
  senderEmail: string;
  senderName: string | null;
  createdAt: Date;
  messages: EmailThreadMessage[];
};

export async function listEmailConversations(): Promise<EmailConversationRow[]> {
  const convs = await prisma.emailConversation.findMany({
    orderBy: { lastMessageAt: "desc" },
    take: 200,
    include: {
      messages: {
        orderBy: { createdAt: "desc" },
        take: 1,
        select: { subject: true, bodyText: true },
      },
      _count: { select: { messages: true } },
    },
  });

  return convs.map((c) => ({
    id: c.id,
    senderEmail: c.senderEmail,
    senderName: c.senderName,
    lastMessageAt: c.lastMessageAt,
    messageCount: c._count.messages,
    lastSubject: c.messages[0]?.subject ?? null,
    lastSnippet: c.messages[0]?.bodyText?.slice(0, 120) ?? null,
  }));
}

export async function getEmailConversation(id: number): Promise<EmailConversationDetail | null> {
  return prisma.emailConversation.findUnique({
    where: { id },
    include: {
      messages: {
        orderBy: { createdAt: "asc" },
        include: {
          attachments: {
            orderBy: { attachmentIndex: "asc" },
            select: {
              id: true,
              attachmentIndex: true,
              fileName: true,
              contentType: true,
              fileSizeBytes: true,
            },
          },
        },
      },
    },
  });
}
