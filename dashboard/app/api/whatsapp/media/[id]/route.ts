import { NextRequest, NextResponse } from "next/server";
import { mkdir, writeFile } from "fs/promises";
import { join } from "path";
import { prisma } from "@/lib/prisma";
import { env } from "@/lib/env";
import { serveFromDisk, guessExtension } from "@/lib/media-storage";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const media = await prisma.whatsAppMedia.findUnique({
    where: { id: Number(id) },
  });
  if (!media) return NextResponse.json({ error: "not found" }, { status: 404 });

  if (media.localPath) {
    const diskResponse = await serveFromDisk(media.localPath, media.contentType);
    if (diskResponse) return diskResponse;
  }

  const sid = process.env.TWILIO_ACCOUNT_SID;
  const token = process.env.TWILIO_AUTH_TOKEN;
  if (!sid || !token) {
    return NextResponse.json({ error: "twilio not configured" }, { status: 503 });
  }

  const auth = "Basic " + Buffer.from(`${sid}:${token}`).toString("base64");
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

  // Lazy backfill: save to disk for future requests
  if (!media.localPath) {
    try {
      const ext = guessExtension(media.contentType);
      const filename = `${media.messageId}_${media.mediaIndex}${ext}`;
      await mkdir(env.whatsappMediaDir, { recursive: true });
      const localPath = join(env.whatsappMediaDir, filename);
      const buffer = Buffer.from(body);
      await writeFile(localPath, buffer);
      await prisma.whatsAppMedia.update({
        where: { id: media.id },
        data: { localPath, fileSizeBytes: buffer.length },
      });
    } catch (err) {
      console.error("Failed to backfill WhatsApp media to disk:", err);
    }
  }

  return new NextResponse(body, {
    headers: {
      "Content-Type": media.contentType,
      "Cache-Control": "private, max-age=3600",
    },
  });
}
