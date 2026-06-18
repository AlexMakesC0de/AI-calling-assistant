import Link from "next/link";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { MessageCircle } from "lucide-react";
import { listConversations } from "@/lib/whatsapp";
import { cn } from "@/lib/utils";
import { TimeAgo } from "@/components/time-ago";
import { EmptyState } from "@/components/empty-state";

export const dynamic = "force-dynamic";
export const metadata = { title: "WhatsApp" };

export default async function WhatsAppPage() {
  const conversations = await listConversations();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-medium tracking-tight">WhatsApp</h1>
        <p className="text-sm text-muted-foreground">
          Inbound and outbound WhatsApp conversations. Voice notes are forwarded to the transcription pipeline.
        </p>
      </div>

      {conversations.length === 0 ? (
        <EmptyState
          icon={MessageCircle}
          title="No conversations yet."
          description="Configure the Twilio WhatsApp sandbox and send a message to get started."
        />
      ) : (
        <div className="rounded-md border border-border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Contact</TableHead>
                <TableHead>Last message</TableHead>
                <TableHead>Preview</TableHead>
                <TableHead className="text-right">Messages</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {conversations.map((conv) => (
                <TableRow key={conv.id}>
                  <TableCell>
                    <Link href={`/whatsapp/${conv.id}`} target="_blank" className="hover:underline">
                      <div className="font-medium">{conv.contactName || conv.contactPhone}</div>
                      {conv.contactName && (
                        <div className="font-mono text-xs text-muted-foreground">{conv.contactPhone}</div>
                      )}
                    </Link>
                  </TableCell>
                  <TableCell className="text-sm"><TimeAgo date={conv.lastMessageAt} /></TableCell>
                  <TableCell className="max-w-[360px]">
                    <div className="flex items-center gap-2 truncate">
                      {conv.lastDirection && (
                        <span className="shrink-0 text-xs text-muted-foreground">
                          {conv.lastDirection === "inbound" ? "←" : "→"}
                        </span>
                      )}
                      {conv.lastType && conv.lastType !== "text" && (
                        <TypeBadge type={conv.lastType} />
                      )}
                      <span className="truncate text-sm text-muted-foreground">
                        {conv.lastBody || mediaLabel(conv.lastType)}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell className="text-right text-sm tabular-nums">{conv.messageCount}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

function TypeBadge({ type }: { type: string }) {
  const labels: Record<string, string> = {
    voice_note: "voice",
    image: "image",
    document: "doc",
    video: "video",
    sticker: "sticker",
    location: "location",
  };
  return (
    <Badge variant="muted" className="shrink-0 text-xs">
      {labels[type] ?? type}
    </Badge>
  );
}

function mediaLabel(type: string | null): string {
  if (!type || type === "text") return "";
  const map: Record<string, string> = {
    voice_note: "[Voice note]",
    image: "[Image]",
    document: "[Document]",
    video: "[Video]",
    sticker: "[Sticker]",
    location: "[Location]",
  };
  return map[type] ?? "[Media]";
}
