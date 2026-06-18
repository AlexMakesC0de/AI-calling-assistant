import { NextRequest, NextResponse } from "next/server";
import { createHmac, timingSafeEqual } from "crypto";
import { prisma } from "@/lib/prisma";

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

export async function POST(req: NextRequest) {
  const authToken = process.env.TWILIO_AUTH_TOKEN;
  if (authToken) {
    const signature = req.headers.get("x-twilio-signature") ?? "";
    const formClone = await req.clone().formData();
    const params: Record<string, string> = {};
    formClone.forEach((v, k) => { params[k] = String(v); });
    if (!validateTwilioSignature(authToken, req.url, params, signature)) {
      return new NextResponse("Forbidden", { status: 403 });
    }
  }

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
