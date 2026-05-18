import { NextResponse } from "next/server";
import { fetchOutlookAttachmentValue } from "@/lib/outlook";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Streams an Outlook attachment through the dashboard so the browser hits a
// same-origin URL. Graph's $value endpoint returns the raw file bytes with
// the appropriate Content-Type/Content-Disposition.
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string; attId: string }> }
) {
  const { id, attId } = await params;
  let upstream: Response;
  try {
    upstream = await fetchOutlookAttachmentValue(id, attId);
  } catch (err) {
    return new NextResponse(`Outlook attachment fetch failed: ${err instanceof Error ? err.message : String(err)}`, {
      status: 502,
    });
  }
  if (!upstream.ok || !upstream.body) {
    return new NextResponse(`Graph returned ${upstream.status}`, { status: upstream.status });
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
