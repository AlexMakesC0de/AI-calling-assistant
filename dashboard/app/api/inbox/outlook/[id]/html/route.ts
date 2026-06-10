import { NextResponse } from "next/server";
import { getOutlookMessage } from "@/lib/outlook";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Returns the HTML body of an Outlook message wrapped in a minimal HTML
// document so the iframe can render fonts/images correctly. The iframe is
// sandboxed at the parent level — we additionally set CSP frame-ancestors
// so the body can't be embedded elsewhere.
export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let message;
  try {
    message = await getOutlookMessage(id);
  } catch (err) {
    return new NextResponse(`Outlook fetch failed: ${err instanceof Error ? err.message : String(err)}`, {
      status: 502,
    });
  }
  const content = message.body?.content ?? "";
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
