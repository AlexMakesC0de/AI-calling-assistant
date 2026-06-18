import { NextResponse } from "next/server";
import { env } from "@/lib/env";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const body = await request.json();
  const transcript: string | undefined = body.transcript;
  if (!transcript || typeof transcript !== "string" || transcript.trim().length === 0) {
    return NextResponse.json({ error: "transcript is required" }, { status: 400 });
  }

  const formatterUrl = `${env.formatterBaseUrl}/format`;
  const res = await fetch(formatterUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      transcript,
      metadata: body.metadata ?? {},
    }),
    signal: AbortSignal.timeout(120_000),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    return NextResponse.json(
      { error: `Formatter responded ${res.status}`, detail: text },
      { status: 502 },
    );
  }

  const data = await res.json();
  return NextResponse.json(data);
}
