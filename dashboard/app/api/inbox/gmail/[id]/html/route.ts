import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { getValidGmailToken } from "@/lib/gmail-oauth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const session = await getSession();
  if (!session) return new NextResponse("Unauthorized", { status: 401 });

  const creds = await getValidGmailToken(session.accountId);
  if (!creds) return new NextResponse("Gmail not connected", { status: 502 });

  const res = await fetch(
    `https://gmail.googleapis.com/gmail/v1/users/me/messages/${encodeURIComponent(id)}?format=full`,
    { headers: { Authorization: `Bearer ${creds.token}` }, cache: "no-store" },
  );
  if (!res.ok) return new NextResponse(`Gmail API error: ${res.status}`, { status: 502 });

  const msg = (await res.json()) as GmailMessage;
  const html = extractBody(msg, "text/html") || `<pre style="font-family:ui-monospace,monospace;white-space:pre-wrap">${escapeHtml(extractBody(msg, "text/plain") || "")}</pre>`;

  return new NextResponse(html, {
    status: 200,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "no-store",
      "Content-Security-Policy": "frame-ancestors 'self'",
    },
  });
}

type GmailPart = {
  mimeType: string;
  body?: { data?: string; size?: number };
  parts?: GmailPart[];
};

type GmailMessage = {
  payload: GmailPart;
};

function extractBody(msg: GmailMessage, mimeType: string): string | null {
  function find(part: GmailPart): string | null {
    if (part.mimeType === mimeType && part.body?.data) {
      return Buffer.from(part.body.data, "base64url").toString("utf-8");
    }
    if (part.parts) {
      for (const sub of part.parts) {
        const result = find(sub);
        if (result) return result;
      }
    }
    return null;
  }
  return find(msg.payload);
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
