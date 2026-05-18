import Link from "next/link";
import { notFound } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { prisma } from "@/lib/prisma";
import {
  flattenAddresses,
  getOutlookMessage,
  listOutlookAttachments,
  outlookConfigured,
  type OutlookAttachmentMeta,
  type OutlookMessage,
} from "@/lib/outlook";
import { formatDateTime } from "@/lib/utils";

export const dynamic = "force-dynamic";

function extractFormId(subject: string | undefined): string | null {
  if (!subject) return null;
  const match = subject.match(/Incident Form (?:Completed|Sent|Generated)\s*[\-–:]\s*([\w-]+)/i);
  return match?.[1] ?? null;
}

async function findIncidentByFormId(formId: string | null): Promise<{ id: number } | null> {
  if (!formId) return null;
  return prisma.incidentGeneralInformation
    .findFirst({
      where: { formData: { path: ["form_id"], equals: formId } },
      select: { incidentFormId: true },
    })
    .then((row) => (row ? { id: row.incidentFormId } : null));
}

export default async function OutlookMessagePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!outlookConfigured()) notFound();

  let message: OutlookMessage;
  let attachments: OutlookAttachmentMeta[] = [];
  try {
    message = await getOutlookMessage(id);
    attachments = message.hasAttachments ? await listOutlookAttachments(id) : [];
  } catch {
    notFound();
  }

  const formId = extractFormId(message.subject);
  const incident = await findIncidentByFormId(formId);

  const isHtml = message.body?.contentType === "html" && Boolean(message.body.content?.trim());

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h1 className="text-2xl font-medium tracking-tight">{message.subject || "(no subject)"}</h1>
          <p className="text-xs text-muted-foreground">{formatDateTime(message.receivedDateTime)}</p>
          {message.importance === "high" ? (
            <Badge variant="solid" className="mt-1">high importance</Badge>
          ) : null}
        </div>
        <div className="flex items-center gap-3">
          {message.webLink ? (
            <a
              href={message.webLink}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-muted-foreground underline underline-offset-4 hover:text-foreground"
            >
              Open in Outlook ↗
            </a>
          ) : null}
          <Link href="/inbox/outlook" className="text-sm text-muted-foreground hover:text-foreground">
            ← Back to Outlook
          </Link>
        </div>
      </div>

      {incident || formId ? (
        <Card>
          <CardContent className="flex items-center justify-between py-3 text-sm">
            <div>
              <span className="text-muted-foreground">Incident form:</span>{" "}
              {incident ? (
                <Link href={`/incidents/${incident.id}`} className="underline underline-offset-4">
                  Open incident #{incident.id}
                </Link>
              ) : (
                <span className="font-mono text-xs">{formId} (not found in DB)</span>
              )}
            </div>
            {formId ? <span className="font-mono text-xs text-muted-foreground">{formId}</span> : null}
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Headers</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <Row label="From">
            <span className="font-mono text-xs">{message.from?.emailAddress?.address ?? "—"}</span>
            {message.from?.emailAddress?.name ? (
              <span className="ml-2 text-muted-foreground">{message.from.emailAddress.name}</span>
            ) : null}
          </Row>
          <Row label="To">
            <span className="font-mono text-xs">{flattenAddresses(message.toRecipients) || "—"}</span>
          </Row>
          {message.ccRecipients && message.ccRecipients.length > 0 ? (
            <Row label="CC"><span className="font-mono text-xs">{flattenAddresses(message.ccRecipients)}</span></Row>
          ) : null}
          {message.bccRecipients && message.bccRecipients.length > 0 ? (
            <Row label="BCC"><span className="font-mono text-xs">{flattenAddresses(message.bccRecipients)}</span></Row>
          ) : null}
          {message.replyTo && message.replyTo.length > 0 ? (
            <Row label="Reply-To"><span className="font-mono text-xs">{flattenAddresses(message.replyTo)}</span></Row>
          ) : null}
          {message.internetMessageId ? (
            <Row label="Message-ID">
              <span className="font-mono text-xs">{message.internetMessageId}</span>
            </Row>
          ) : null}
          <Row label="Read">{message.isRead ? "Yes" : "No"}</Row>
        </CardContent>
      </Card>

      {attachments.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Attachments ({attachments.length})</CardTitle>
          </CardHeader>
          <CardContent className="divide-y divide-border p-0">
            {attachments.map((att) => (
              <div key={att.id} className="flex items-center justify-between gap-3 px-6 py-3 text-sm">
                <div className="min-w-0">
                  <div className="truncate font-mono text-xs">{att.name}</div>
                  <div className="text-xs text-muted-foreground">
                    {att.contentType} · {Math.round(att.size / 1024)} KB
                    {att.isInline ? " · inline" : null}
                  </div>
                </div>
                <a
                  href={`/api/inbox/outlook/${encodeURIComponent(message.id)}/attachments/${encodeURIComponent(att.id)}`}
                  className="text-xs underline underline-offset-4"
                  download={att.name}
                >
                  Download
                </a>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Body</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {isHtml ? (
            <iframe
              src={`/api/inbox/outlook/${encodeURIComponent(message.id)}/html`}
              className="h-[600px] w-full rounded-md border border-border bg-background"
              sandbox="allow-same-origin"
              title={message.subject || "Email body"}
            />
          ) : (
            <>
              {message.body?.content?.trim() ? (
                <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-md border border-border bg-muted/30 p-3 font-mono text-xs leading-relaxed">
                  {message.body.content}
                </pre>
              ) : (
                <p className="text-sm text-muted-foreground">Empty body.</p>
              )}
            </>
          )}
          {isHtml && message.bodyPreview ? (
            <>
              <Separator />
              <div>
                <div className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">Preview</div>
                <p className="text-xs text-muted-foreground">{message.bodyPreview}</p>
              </div>
            </>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline gap-3">
      <div className="w-24 shrink-0 text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="flex-1">{children}</div>
    </div>
  );
}
