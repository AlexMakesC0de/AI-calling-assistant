import { prisma } from "@/lib/prisma";

export type CallConversationRow = {
  id: number;
  contactPhone: string;
  contactName: string | null;
  lastCallAt: Date;
  callCount: number;
  lastStatus: string | null;
  lastDuration: number | null;
  lastDirection: string | null;
};

export async function listConversations(): Promise<CallConversationRow[]> {
  const convs = await prisma.callConversation.findMany({
    orderBy: { lastCallAt: "desc" },
    take: 200,
    include: {
      calls: {
        orderBy: { createdAt: "desc" },
        take: 1,
        select: { status: true, durationSeconds: true, direction: true },
      },
      _count: { select: { calls: true } },
    },
  });

  return convs.map((c) => ({
    id: c.id,
    contactPhone: c.contactPhone,
    contactName: c.contactName,
    lastCallAt: c.lastCallAt,
    callCount: c._count.calls,
    lastStatus: c.calls[0]?.status ?? null,
    lastDuration: c.calls[0]?.durationSeconds ?? null,
    lastDirection: c.calls[0]?.direction ?? null,
  }));
}

export type CallDetail = {
  id: number;
  callSid: string;
  direction: string;
  fromNumber: string | null;
  toNumber: string | null;
  status: string;
  durationSeconds: number | null;
  recordingSid: string | null;
  recordingTwilioUrl: string | null;
  localRecordingPath: string | null;
  incidentFormId: number | null;
  transcriptText: string | null;
  errorMessage: string | null;
  createdAt: Date;
};

export type CallConversationDetail = {
  id: number;
  contactPhone: string;
  contactName: string | null;
  createdAt: Date;
  calls: CallDetail[];
};

export async function getConversation(id: number): Promise<CallConversationDetail | null> {
  const conv = await prisma.callConversation.findUnique({
    where: { id },
    include: {
      calls: {
        orderBy: { createdAt: "desc" },
        select: {
          id: true,
          callSid: true,
          direction: true,
          fromNumber: true,
          toNumber: true,
          status: true,
          durationSeconds: true,
          recordingSid: true,
          recordingTwilioUrl: true,
          localRecordingPath: true,
          incidentFormId: true,
          transcriptText: true,
          errorMessage: true,
          createdAt: true,
        },
      },
    },
  });
  return conv;
}

export async function getCallById(callId: number) {
  return prisma.twilioCall.findUnique({ where: { id: callId } });
}
