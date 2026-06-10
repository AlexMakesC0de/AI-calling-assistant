import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

export async function POST(req: NextRequest) {
  const formData = await req.formData();
  const sid = formData.get("MessageSid") as string | null;
  const status = formData.get("MessageStatus") as string | null;

  if (sid && status) {
    await prisma.whatsAppMessage.updateMany({
      where: { twilioSid: sid },
      data: { status },
    });
  }

  return new NextResponse(null, { status: 204 });
}
