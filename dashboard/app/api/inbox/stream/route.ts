import { listMailpitMessages } from "@/lib/mailpit";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Server-Sent Events stream that polls Mailpit every few seconds and pushes a
// `tick` event when the inbox total or unread count changes. The client reacts
// by re-fetching the list — pages get refreshed without a full reload.
//
// We use SSE rather than proxying Mailpit's WebSocket because Next App Router
// doesn't natively support upgrading connections; this gives us the same
// near-realtime feel through a much simpler dependency surface.
const POLL_INTERVAL_MS = 3000;

export async function GET(request: Request) {
  const encoder = new TextEncoder();
  let closed = false;

  const stream = new ReadableStream({
    async start(controller) {
      const send = (event: string, data: unknown) => {
        if (closed) return;
        controller.enqueue(encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`));
      };

      let lastTotal = -1;
      let lastUnread = -1;

      const tick = async () => {
        if (closed) return;
        try {
          const list = await listMailpitMessages(1);
          if (list.total !== lastTotal || list.unread !== lastUnread) {
            lastTotal = list.total;
            lastUnread = list.unread;
            send("tick", { total: list.total, unread: list.unread });
          }
        } catch (err) {
          send("error", { message: err instanceof Error ? err.message : String(err) });
        }
      };

      send("hello", { interval: POLL_INTERVAL_MS });
      await tick();
      const interval = setInterval(tick, POLL_INTERVAL_MS);

      request.signal.addEventListener("abort", () => {
        closed = true;
        clearInterval(interval);
        try {
          controller.close();
        } catch {
          // already closed
        }
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
