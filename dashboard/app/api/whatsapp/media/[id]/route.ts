import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const media = await prisma.whatsAppMedia.findUnique({
    where: { id: Number(id) },
  });
  if (!media) return NextResponse.json({ error: "not found" }, { status: 404 });

  const sid = process.env.TWILIO_ACCOUNT_SID;
  const token = process.env.TWILIO_AUTH_TOKEN;
  if (!sid || !token) {
    return NextResponse.json({ error: "twilio not configured" }, { status: 503 });
  }

  const auth = "Basic " + Buffer.from(`${sid}:${token}`).toString("base64");

  // Twilio media URLs redirect to a CDN. Follow manually so the auth
  // header isn't stripped on the cross-origin redirect.
  const initial = await fetch(media.twilioUrl, {
    headers: { Authorization: auth },
    redirect: "manual",
  });

  let res: Response;
  const location = initial.headers.get("location");
  if (initial.status >= 300 && initial.status < 400 && location) {
    res = await fetch(location);
  } else {
    res = initial;
  }

  if (!res.ok) {
    return NextResponse.json(
      { error: "upstream error", status: res.status, url: media.twilioUrl },
      { status: 502 },
    );
  }

  const body = await res.arrayBuffer();
  return new NextResponse(body, {
    headers: {
      "Content-Type": media.contentType,
      "Cache-Control": "private, max-age=3600",
    },
  });
}
