import { NextRequest } from "next/server";
import { getSession } from "@/lib/auth";
import { getAnalysisStatus, type SourceType } from "@/lib/analyze-content";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const POLL_INTERVAL_MS = 1500;

export async function GET(request: NextRequest) {
  const session = await getSession();
  if (!session) {
    return new Response(JSON.stringify({ error: "Not authenticated" }), { status: 401 });
  }

  const sourceType = request.nextUrl.searchParams.get("sourceType") as SourceType | null;
  const sourceId = request.nextUrl.searchParams.get("sourceId");

  if (!sourceType || !sourceId) {
    return new Response(JSON.stringify({ error: "Missing sourceType or sourceId" }), { status: 400 });
  }

  const encoder = new TextEncoder();
  let closed = false;

  const stream = new ReadableStream({
    async start(controller) {
      const send = (event: string, data: unknown) => {
        if (closed) return;
        controller.enqueue(encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`));
      };

      let lastStatus = "";
      let lastStep = "";

      const tick = async () => {
        if (closed) return;
        try {
          const status = await getAnalysisStatus(sourceType, sourceId);
          if (!status) {
            send("status", { pipelineStatus: "not_found" });
            return;
          }

          const key = `${status.pipelineStatus}:${status.pipelineStep}`;
          if (key !== `${lastStatus}:${lastStep}`) {
            lastStatus = status.pipelineStatus;
            lastStep = status.pipelineStep ?? "";
            send("status", status);
          }

          if (status.pipelineStatus === "completed" || status.pipelineStatus === "failed") {
            closed = true;
            clearInterval(interval);
            try { controller.close(); } catch {}
          }
        } catch {
          // DB error, keep trying
        }
      };

      send("hello", { interval: POLL_INTERVAL_MS });
      await tick();
      const interval = setInterval(tick, POLL_INTERVAL_MS);

      request.signal.addEventListener("abort", () => {
        closed = true;
        clearInterval(interval);
        try { controller.close(); } catch {}
      });
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-store, no-transform",
      Connection: "keep-alive",
    },
  });
}
