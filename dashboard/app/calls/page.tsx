import Link from "next/link";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Phone } from "lucide-react";
import { listConversations } from "@/lib/calls";
import { TimeAgo } from "@/components/time-ago";
import { EmptyState } from "@/components/empty-state";

export const dynamic = "force-dynamic";
export const metadata = { title: "Calls" };

function formatDuration(seconds: number | null): string {
  if (seconds == null) return "—";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function statusVariant(status: string | null): "default" | "solid" | "muted" {
  switch (status) {
    case "completed":
    case "transcribed":
      return "muted";
    case "failed":
      return "solid";
    default:
      return "default";
  }
}

export default async function CallsPage() {
  const conversations = await listConversations();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-medium tracking-tight">Calls</h1>
        <p className="text-sm text-muted-foreground">
          Inbound voice call recordings grouped by caller.
        </p>
      </div>

      {conversations.length === 0 ? (
        <EmptyState
          icon={Phone}
          title="No calls yet."
          description="Configure your Twilio phone number webhook to get started."
        />
      ) : (
        <div className="rounded-md border border-border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Caller</TableHead>
                <TableHead>Last call</TableHead>
                <TableHead>Duration</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Calls</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {conversations.map((conv) => (
                <TableRow key={conv.id} className="cursor-pointer">
                  <TableCell>
                    <Link href={`/calls/${conv.id}`} className="hover:underline">
                      <div className="font-medium">{conv.contactName || conv.contactPhone}</div>
                      {conv.contactName && (
                        <div className="font-mono text-xs text-muted-foreground">{conv.contactPhone}</div>
                      )}
                    </Link>
                  </TableCell>
                  <TableCell className="text-sm">
                    <Link href={`/calls/${conv.id}`} className="block"><TimeAgo date={conv.lastCallAt} /></Link>
                  </TableCell>
                  <TableCell className="text-sm tabular-nums">
                    <Link href={`/calls/${conv.id}`} className="block">{formatDuration(conv.lastDuration)}</Link>
                  </TableCell>
                  <TableCell>
                    <Link href={`/calls/${conv.id}`} className="block">
                      {conv.lastStatus && (
                        <Badge variant={statusVariant(conv.lastStatus)}>
                          {conv.lastStatus}
                        </Badge>
                      )}
                    </Link>
                  </TableCell>
                  <TableCell className="text-right text-sm tabular-nums">
                    <Link href={`/calls/${conv.id}`} className="block">{conv.callCount}</Link>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
