import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

export async function POST(req: NextRequest) {
  const formData = await req.formData();
  const form: Record<string, string> = {};
  formData.forEach((v, k) => {
    form[k] = String(v);
  });

  const callSid = form["CallSid"] ?? "";
  const callStatus = form["CallStatus"] ?? "";
  const errorCode = form["ErrorCode"] ?? null;
  const errorMessage = form["ErrorMessage"] ?? null;

  console.log(
    `[call-status] CallSid=${callSid} status=${callStatus} error=${errorCode}`,
  );

  if (callSid && callStatus) {
    try {
      await prisma.twilioCall.updateMany({
        where: { callSid },
        data: {
          status: callStatus,
          errorCode,
          errorMessage,
        },
      });
    } catch (err) {
      console.error("[call-status] DB update failed:", err);
    }
  }

  return new NextResponse(null, { status: 204 });
}
