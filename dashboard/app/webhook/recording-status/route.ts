import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

export async function POST(req: NextRequest) {
  const formData = await req.formData();
  const form: Record<string, string> = {};
  formData.forEach((v, k) => {
    form[k] = String(v);
  });

  const callSid = form["CallSid"] ?? "";
  const recordingSid = form["RecordingSid"] ?? "";
  const recordingUrl = form["RecordingUrl"] ?? "";
  const recordingDuration = form["RecordingDuration"];
  const fromNumber = form["From"] ?? "";
  const toNumber = form["To"] ?? "";

  const duration =
    recordingDuration && /^\d+$/.test(recordingDuration)
      ? parseInt(recordingDuration, 10)
      : null;

  console.log(
    `[recording-status] CallSid=${callSid} RecordingSid=${recordingSid} duration=${duration} from=${fromNumber}`,
  );

  try {
    const conversation = await prisma.callConversation.upsert({
      where: { contactPhone: fromNumber },
      update: { lastCallAt: new Date() },
      create: { contactPhone: fromNumber, lastCallAt: new Date() },
    });

    await prisma.twilioCall.upsert({
      where: { callSid },
      update: {
        status: "recorded",
        durationSeconds: duration ?? undefined,
        recordingSid: recordingSid || undefined,
        recordingTwilioUrl: recordingUrl || undefined,
      },
      create: {
        conversationId: conversation.id,
        callSid,
        direction: "inbound",
        fromNumber,
        toNumber,
        status: "recorded",
        durationSeconds: duration,
        recordingSid: recordingSid || null,
        recordingTwilioUrl: recordingUrl || null,
      },
    });
  } catch (err) {
    console.error("[recording-status] DB insert failed:", err);
  }

  return new NextResponse(null, { status: 204 });
}
