import { NextRequest, NextResponse } from "next/server";
import { mkdir, writeFile } from "fs/promises";
import { join } from "path";
import { prisma } from "@/lib/prisma";
import { env } from "@/lib/env";
import { serveFromDisk } from "@/lib/media-storage";
import { fetchRecordingMp3 } from "@/lib/calls";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const call = await prisma.twilioCall.findUnique({
    where: { id: Number(id) },
  });
  if (!call) return NextResponse.json({ error: "not found" }, { status: 404 });

  if (call.localRecordingPath) {
    const diskResponse = await serveFromDisk(call.localRecordingPath, "audio/mpeg");
    if (diskResponse) return diskResponse;
  }

  if (!call.recordingTwilioUrl) {
    return NextResponse.json({ error: "no recording available" }, { status: 404 });
  }

  let body: Buffer;
  try {
    body = await fetchRecordingMp3(call.recordingTwilioUrl);
  } catch (err) {
    return NextResponse.json(
      { error: "upstream error", detail: String(err) },
      { status: 502 },
    );
  }

  if (!call.localRecordingPath) {
    try {
      const filename = `${call.callSid}_${call.recordingSid || call.id}.mp3`;
      await mkdir(env.callRecordingsDir, { recursive: true });
      const localPath = join(env.callRecordingsDir, filename);
      await writeFile(localPath, body);
      await prisma.twilioCall.update({
        where: { id: call.id },
        data: { localRecordingPath: localPath },
      });
    } catch (err) {
      console.error("Failed to backfill call recording to disk:", err);
    }
  }

  return new NextResponse(new Uint8Array(body), {
    headers: {
      "Content-Type": "audio/mpeg",
      "Cache-Control": "private, max-age=3600",
    },
  });
}
