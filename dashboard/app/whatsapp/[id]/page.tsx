import Link from "next/link";
import { notFound } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { getConversation, type ThreadMessage } from "@/lib/whatsapp";
import { formatDateTime } from "@/lib/utils";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";

export default async function WhatsAppThreadPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const numericId = Number(id);
  if (!Number.isFinite(numericId)) notFound();

  const conv = await getConversation(numericId);
  if (!conv) notFound();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h1 className="text-2xl font-medium tracking-tight">
            {conv.contactName || conv.contactPhone}
          </h1>
          {conv.contactName && (
            <p className="font-mono text-xs text-muted-foreground">{conv.contactPhone}</p>
          )}
        </div>
        <Link href="/whatsapp" className="text-sm text-muted-foreground hover:text-foreground">
          ← Back to conversations
        </Link>
      </div>

      {conv.messages.length === 0 ? (
        <div className="rounded-md border border-border p-12 text-center text-sm text-muted-foreground">
          No messages in this conversation.
        </div>
      ) : (
        <div className="space-y-3">
          {conv.messages.map((msg) => (
            <MessageBubble key={msg.id} msg={msg} />
          ))}
        </div>
      )}
    </div>
  );
}

function MessageBubble({ msg }: { msg: ThreadMessage }) {
  const isOutbound = msg.direction === "outbound";

  return (
    <div className={cn("flex", isOutbound ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[75%] space-y-1.5 rounded-2xl px-4 py-3 text-sm",
          isOutbound
            ? "rounded-tr-sm bg-foreground text-background"
            : "rounded-tl-sm border border-border bg-muted/30"
        )}
      >
        {/* type badge for non-text messages */}
        {msg.messageType !== "text" && (
          <div>
            <TypeBadge type={msg.messageType} outbound={isOutbound} />
          </div>
        )}

        {/* body text */}
        {msg.body && (
          <p className="whitespace-pre-wrap leading-relaxed">{msg.body}</p>
        )}

        {/* media attachments */}
        {msg.media.length > 0 && (
          <div className="space-y-1">
            {msg.media.map((m) => (
              <MediaRow key={m.id} media={m} outbound={isOutbound} />
            ))}
          </div>
        )}

        {/* voice note → incident form link */}
        {msg.messageType === "voice_note" && msg.incidentFormId && (
          <div>
            <Link
              href={`/incidents/${msg.incidentFormId}`}
              className={cn(
                "text-xs underline underline-offset-4",
                isOutbound ? "text-background/70 hover:text-background" : "text-muted-foreground hover:text-foreground"
              )}
            >
              View incident #{msg.incidentFormId} →
            </Link>
          </div>
        )}

        {/* voice note pending (no form yet) */}
        {msg.messageType === "voice_note" && !msg.incidentFormId && (
          <p className={cn("text-xs", isOutbound ? "text-background/60" : "text-muted-foreground")}>
            Processing…
          </p>
        )}

        {/* timestamp + status */}
        <div
          className={cn(
            "flex items-center gap-2 text-xs",
            isOutbound ? "justify-end text-background/60" : "text-muted-foreground"
          )}
        >
          <span>{formatDateTime(msg.createdAt)}</span>
          {isOutbound && <StatusDot status={msg.status} />}
        </div>
      </div>
    </div>
  );
}

function MediaRow({
  media,
  outbound,
}: {
  media: ThreadMessage["media"][number];
  outbound: boolean;
}) {
  const isImage = media.contentType.startsWith("image/");
  const isAudio = media.contentType.startsWith("audio/");
  const isVideo = media.contentType.startsWith("video/");
  const proxyUrl = `/api/whatsapp/media/${media.id}`;

  if (isImage) {
    return (
      <a href={proxyUrl} target="_blank" rel="noopener noreferrer">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={proxyUrl}
          alt="WhatsApp image"
          className="max-h-64 rounded-lg"
          loading="lazy"
        />
      </a>
    );
  }

  if (isAudio) {
    return (
      <audio controls preload="none" className="max-w-full">
        <source src={proxyUrl} type={media.contentType} />
      </audio>
    );
  }

  if (isVideo) {
    return (
      <video controls preload="none" className="max-h-64 max-w-full rounded-lg">
        <source src={proxyUrl} type={media.contentType} />
      </video>
    );
  }

  return (
    <a
      href={proxyUrl}
      target="_blank"
      rel="noopener noreferrer"
      className={cn(
        "flex items-center gap-2 rounded-md border px-3 py-2 text-xs hover:bg-muted/50 transition-colors",
        outbound ? "border-background/30" : "border-border"
      )}
    >
      <span>📎</span>
      <span className="truncate font-mono">
        {media.localPath ? media.localPath.split("/").pop() : media.contentType}
      </span>
      <span className="ml-auto shrink-0 text-[10px] opacity-60">Download</span>
    </a>
  );
}

function TypeBadge({ type, outbound }: { type: string; outbound: boolean }) {
  const labels: Record<string, string> = {
    voice_note: "Voice note",
    image: "Image",
    document: "Document",
    video: "Video",
    sticker: "Sticker",
    location: "Location",
  };
  return (
    <span
      className={cn(
        "inline-block rounded-full px-2 py-0.5 text-xs font-medium",
        outbound ? "bg-background/20" : "border border-border bg-background text-foreground"
      )}
    >
      {labels[type] ?? type}
    </span>
  );
}

function StatusDot({ status }: { status: string }) {
  const symbols: Record<string, string> = {
    queued: "○",
    sent: "✓",
    delivered: "✓✓",
    read: "✓✓",
    failed: "✗",
    undelivered: "✗",
    received: "✓",
  };
  return <span title={status}>{symbols[status] ?? status}</span>;
}
