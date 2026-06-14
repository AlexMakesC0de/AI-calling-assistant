import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { getValidGmailToken } from "@/lib/gmail-oauth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string; attId: string }> },
) {
  const { id, attId } = await params;
  const session = await getSession();
  if (!session) return new NextResponse("Unauthorized", { status: 401 });

  const creds = await getValidGmailToken(session.accountId);
  if (!creds) return new NextResponse("Gmail not connected", { status: 502 });

  const res = await fetch(
    `https://gmail.googleapis.com/gmail/v1/users/me/messages/${encodeURIComponent(id)}/attachments/${encodeURIComponent(attId)}`,
    { headers: { Authorization: `Bearer ${creds.token}` }, cache: "no-store" },
  );

  if (!res.ok) {
    return new NextResponse(`Gmail attachment error: ${res.status}`, { status: res.status });
  }

  const data = (await res.json()) as { data: string; size: number };
  const buffer = Buffer.from(data.data, "base64url");

  return new NextResponse(buffer, {
    status: 200,
    headers: {
      "Content-Type": "application/octet-stream",
      "Content-Length": String(buffer.length),
      "Cache-Control": "no-store",
    },
  });
}
