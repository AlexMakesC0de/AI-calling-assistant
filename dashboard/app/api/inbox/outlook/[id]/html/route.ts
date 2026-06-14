import { NextResponse } from "next/server";
import { graphJsonAuto, resolveGraphToken } from "@/lib/outlook-graph";
import { prisma } from "@/lib/prisma";
import type { OutlookAttachmentMeta, OutlookMessage } from "@/lib/outlook";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const resolved = await resolveGraphToken();
  if (!resolved) return new NextResponse("Outlook not connected", { status: 502 });

  let message: OutlookMessage;
  try {
    message = await graphJsonAuto<OutlookMessage>(
      `${resolved.userPath}/messages/${encodeURIComponent(id)}`,
    );
  } catch (err) {
    return new NextResponse(`Outlook fetch failed: ${err instanceof Error ? err.message : String(err)}`, {
      status: 502,
    });
  }

  let content = message.body?.content ?? "";

  if (message.body?.contentType === "html" && content.includes("cid:")) {
    try {
      const cached = await prisma.outlookAttachmentCache.findMany({
        where: { messageId: id, isInline: true, contentId: { not: null } },
      });

      if (cached.length > 0) {
        for (const att of cached) {
          if (!att.contentId) continue;
          const cidRef = att.contentId.replace(/^<|>$/g, "");
          const proxyUrl = `/api/inbox/outlook/${encodeURIComponent(id)}/attachments/${encodeURIComponent(att.attachmentId)}`;
          content = content.replace(
            new RegExp(`(src=["'])cid:${escapeRegex(cidRef)}(["'])`, "gi"),
            `$1${proxyUrl}$2`,
          );
        }
      } else {
        const attJson = await graphJsonAuto<{ value: OutlookAttachmentMeta[] }>(
          `${resolved.userPath}/messages/${encodeURIComponent(id)}/attachments?$select=id,name,contentType,size,isInline,contentId`,
        );
        for (const att of attJson.value) {
          if (att.isInline && att.contentId) {
            const cidRef = att.contentId.replace(/^<|>$/g, "");
            const proxyUrl = `/api/inbox/outlook/${encodeURIComponent(id)}/attachments/${encodeURIComponent(att.id)}`;
            content = content.replace(
              new RegExp(`(src=["'])cid:${escapeRegex(cidRef)}(["'])`, "gi"),
              `$1${proxyUrl}$2`,
            );
          }
        }
      }
    } catch (err) {
      console.error("CID rewrite failed:", err);
    }
  }

  const html = message.body?.contentType === "html"
    ? content
    : `<pre style="font-family:ui-monospace,monospace;white-space:pre-wrap">${escapeHtml(content)}</pre>`;
  return new NextResponse(html, {
    status: 200,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "no-store",
      "Content-Security-Policy": "frame-ancestors 'self'",
    },
  });
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
