import { NextResponse } from "next/server";
import { mkdir, writeFile } from "fs/promises";
import { join } from "path";
import { graphFetchAuto, graphJsonAuto, resolveGraphToken } from "@/lib/outlook-graph";
import { prisma } from "@/lib/prisma";
import { env } from "@/lib/env";
import { sanitizeFilename, serveFromDisk } from "@/lib/media-storage";
import type { OutlookAttachmentMeta } from "@/lib/outlook";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string; attId: string }> },
) {
  const { id, attId } = await params;
  const resolved = await resolveGraphToken();
  if (!resolved) return new NextResponse("Outlook not connected", { status: 502 });

  const cached = await prisma.outlookAttachmentCache.findUnique({
    where: { messageId_attachmentId: { messageId: id, attachmentId: attId } },
  });

  if (cached) {
    const diskResponse = await serveFromDisk(cached.localPath, cached.contentType);
    if (diskResponse) {
      if (cached.fileName) {
        diskResponse.headers.set("Content-Disposition", `attachment; filename="${cached.fileName}"`);
      }
      return diskResponse;
    }
  }

  const msgPath = `${resolved.userPath}/messages/${encodeURIComponent(id)}`;

  let meta: OutlookAttachmentMeta;
  try {
    meta = await graphJsonAuto<OutlookAttachmentMeta>(
      `${msgPath}/attachments/${encodeURIComponent(attId)}?$select=id,name,contentType,size,isInline,contentId`,
    );
  } catch (err) {
    return new NextResponse(`Attachment metadata fetch failed: ${err instanceof Error ? err.message : String(err)}`, {
      status: 502,
    });
  }

  let upstream: Response;
  try {
    upstream = await graphFetchAuto(
      `${msgPath}/attachments/${encodeURIComponent(attId)}/$value`,
    );
  } catch (err) {
    return new NextResponse(`Outlook attachment fetch failed: ${err instanceof Error ? err.message : String(err)}`, {
      status: 502,
    });
  }
  if (!upstream.ok || !upstream.body) {
    return new NextResponse(`Graph returned ${upstream.status}`, { status: upstream.status });
  }

  const buffer = Buffer.from(await upstream.arrayBuffer());

  try {
    const cacheDir = join(env.outlookAttachmentsDir, sanitizeFilename(id));
    const safeName = `${sanitizeFilename(attId)}_${sanitizeFilename(meta.name || "file")}`;
    const localPath = join(cacheDir, safeName);
    await mkdir(cacheDir, { recursive: true });
    await writeFile(localPath, buffer);

    await prisma.outlookAttachmentCache.upsert({
      where: { messageId_attachmentId: { messageId: id, attachmentId: attId } },
      update: { localPath, fileSizeBytes: buffer.length },
      create: {
        messageId: id,
        attachmentId: attId,
        fileName: meta.name || null,
        contentType: meta.contentType,
        localPath,
        fileSizeBytes: buffer.length,
        contentId: meta.contentId ?? null,
        isInline: meta.isInline,
      },
    });
  } catch (err) {
    console.error("Failed to cache Outlook attachment:", err);
  }

  const headers = new Headers();
  headers.set("Content-Type", meta.contentType);
  if (meta.name) headers.set("Content-Disposition", `attachment; filename="${meta.name}"`);
  headers.set("Cache-Control", "private, max-age=3600");
  return new NextResponse(buffer, { status: 200, headers });
}
