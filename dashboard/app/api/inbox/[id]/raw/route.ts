import { NextResponse } from "next/server";
import { fetchMailpitRaw } from "@/lib/mailpit";

export const runtime = "nodejs";

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const upstream = await fetchMailpitRaw(id);
  if (!upstream.ok || !upstream.body) {
    return new NextResponse(`Mailpit returned ${upstream.status}`, { status: upstream.status });
  }
  return new NextResponse(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": "message/rfc822",
      "Content-Disposition": `attachment; filename="${id}.eml"`,
      "Cache-Control": "no-store",
    },
  });
}
