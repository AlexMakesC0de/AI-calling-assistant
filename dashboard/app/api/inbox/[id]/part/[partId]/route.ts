import { NextResponse } from "next/server";
import { fetchMailpitPart } from "@/lib/mailpit";

export const runtime = "nodejs";

// Streams an attachment from Mailpit through the dashboard so the browser can
// download from a same-origin URL even when Mailpit is only reachable via the
// docker network.
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string; partId: string }> }
) {
  const { id, partId } = await params;
  const upstream = await fetchMailpitPart(id, partId);
  if (!upstream.ok || !upstream.body) {
    return new NextResponse(`Mailpit returned ${upstream.status}`, { status: upstream.status });
  }
  const headers = new Headers();
  const contentType = upstream.headers.get("content-type");
  if (contentType) headers.set("Content-Type", contentType);
  const disposition = upstream.headers.get("content-disposition");
  if (disposition) headers.set("Content-Disposition", disposition);
  const length = upstream.headers.get("content-length");
  if (length) headers.set("Content-Length", length);
  headers.set("Cache-Control", "no-store");
  return new NextResponse(upstream.body, { status: 200, headers });
}
