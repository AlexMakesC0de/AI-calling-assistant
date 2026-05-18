import { NextResponse } from "next/server";
import { env } from "@/lib/env";

export const runtime = "nodejs";

// Proxies Mailpit's pre-rendered HTML preview through the dashboard so the
// browser can hit a same-origin URL even when Mailpit is only reachable via the
// in-cluster docker network (e.g. http://mailpit:8025).
export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const url = `${env.mailpitBaseUrl}/view/${encodeURIComponent(id)}.html`;

  const upstream = await fetch(url, { cache: "no-store" });
  if (!upstream.ok) {
    return new NextResponse(`Mailpit returned ${upstream.status}`, { status: upstream.status });
  }
  const html = await upstream.text();
  return new NextResponse(html, {
    status: 200,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      // We don't want browsers caching potentially-evolving Mailpit content.
      "Cache-Control": "no-store",
      // Defence-in-depth: this iframe is sandboxed but we also forbid framing from anywhere else.
      "Content-Security-Policy": "frame-ancestors 'self'",
    },
  });
}
