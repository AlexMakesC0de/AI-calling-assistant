import Link from "next/link";
import { notFound } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { prisma } from "@/lib/prisma";
import {
  flattenAddresses,
  type OutlookAttachmentMeta,
  type OutlookMessage,
} from "@/lib/outlook";
import { graphJsonAuto, resolveGraphToken } from "@/lib/outlook-graph";
import { getValidGmailToken } from "@/lib/gmail-oauth";
import { getSession } from "@/lib/auth";
import { formatDateTime } from "@/lib/utils";
import { getExistingAnalysis, type SourceType } from "@/lib/analyze-content";
import { CopyButton } from "@/components/copy-button";
import { EmailAnalyzeWrapper } from "./email-analyze-wrapper";
import { SaveEmailButton } from "./save-email-button";

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

type GmailHeader = { name: string; value: string };
type GmailPart = {
  mimeType: string;
  filename?: string;
  body?: { data?: string; size?: number; attachmentId?: string };
  parts?: GmailPart[];
  headers?: GmailHeader[];
};
type GmailFullMessage = {
  id: string;
  snippet: string;
  labelIds: string[];
  internalDate: string;
  payload: GmailPart & { headers: GmailHeader[] };
};

function getHeader(headers: GmailHeader[], name: string): string {
  return headers.find((h) => h.name.toLowerCase() === name.toLowerCase())?.value ?? "";
}

function extractBody(part: GmailPart, mimeType: string): string | null {
  if (part.mimeType === mimeType && part.body?.data) {
    return Buffer.from(part.body.data, "base64url").toString("utf-8");
  }
  if (part.parts) {
    for (const sub of part.parts) {
      const result = extractBody(sub, mimeType);
      if (result) return result;
    }
  }
  return null;
}

type GmailAttachment = { id: string; name: string; contentType: string; size: number };

function collectAttachments(part: GmailPart): GmailAttachment[] {
  const result: GmailAttachment[] = [];
  if (part.filename && part.body?.attachmentId) {
    result.push({
      id: part.body.attachmentId,
      name: part.filename,
      contentType: part.mimeType,
      size: part.body.size ?? 0,
    });
  }
  if (part.parts) {
    for (const sub of part.parts) result.push(...collectAttachments(sub));
  }
  return result;
}

export default async function MessageDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: rawId } = await params;
  const isGmail = rawId.startsWith("gmail-");
  const id = isGmail ? rawId.slice(6) : rawId;

  if (isGmail) {
    return renderGmailMessage(id);
  }
  return renderOutlookMessage(id);
}

async function renderGmailMessage(id: string) {
  const session = await getSession();
  if (!session) notFound();

  const creds = await getValidGmailToken(session.accountId);
  if (!creds) notFound();

  const res = await fetch(
    `https://gmail.googleapis.com/gmail/v1/users/me/messages/${encodeURIComponent(id)}?format=full`,
    { headers: { Authorization: `Bearer ${creds.token}` }, cache: "no-store" },
  );
  if (!res.ok) notFound();

  const msg = (await res.json()) as GmailFullMessage;
  const subject = getHeader(msg.payload.headers, "Subject") || "(no subject)";
  const from = getHeader(msg.payload.headers, "From");
  const to = getHeader(msg.payload.headers, "To");
  const cc = getHeader(msg.payload.headers, "Cc");
  const date = new Date(Number(msg.internalDate)).toISOString();
  const messageId = getHeader(msg.payload.headers, "Message-ID");
  const isRead = !msg.labelIds.includes("UNREAD");

  const htmlBody = extractBody(msg.payload, "text/html");
  const textBody = extractBody(msg.payload, "text/plain");
  const isHtml = Boolean(htmlBody);
  const attachments = collectAttachments(msg.payload);

  const formId = extractFormId(subject);
  const incident = await findIncidentByFormId(formId);
  const analysis = await getExistingAnalysis("gmail_email" as SourceType, id);
  const analysisProps = analysis?.pipeline_status ? {
    label: analysis.classification_label ?? "unknown",
    confidence: analysis.classification_confidence ?? 0,
    reason: analysis.classification_reason ?? "",
    incidentFormId: analysis.incident_form_id,
    pipelineStatus: analysis.pipeline_status,
    errorMessage: analysis.error_message,
  } : null;

  const savedEmail = await prisma.emailMessage.findFirst({
    where: { messageIdHeader: messageId || id },
    select: { id: true },
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h1 className="text-2xl font-medium tracking-tight">{subject}</h1>
          <p className="text-xs text-muted-foreground">{formatDateTime(date)}</p>
        </div>
        <div className="flex items-center gap-3">
          <SaveEmailButton messageId={id} provider="google" alreadySaved={!!savedEmail} />
          <Link href="/inbox/outlook" className="text-sm text-muted-foreground hover:text-foreground">
            ← Back
          </Link>
        </div>
      </div>

      {(incident || formId) && (
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
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle>AI Analysis</CardTitle></CardHeader>
        <CardContent>
          <EmailAnalyzeWrapper messageId={id} provider="google" existingAnalysis={analysisProps} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Headers</CardTitle></CardHeader>
        <CardContent className="space-y-2 text-sm">
          <Row label="From">
            <span className="inline-flex items-center gap-1.5 font-mono text-xs">
              {from || "—"} {from && <CopyButton value={from} />}
            </span>
          </Row>
          <Row label="To">
            <span className="inline-flex items-center gap-1.5 font-mono text-xs">
              {to || "—"} {to && <CopyButton value={to} />}
            </span>
          </Row>
          {cc && <Row label="CC"><span className="inline-flex items-center gap-1.5 font-mono text-xs">{cc} <CopyButton value={cc} /></span></Row>}
          {messageId && <Row label="Message-ID"><span className="inline-flex items-center gap-1.5 font-mono text-xs">{messageId} <CopyButton value={messageId} /></span></Row>}
          <Row label="Read">{isRead ? "Yes" : "No"}</Row>
        </CardContent>
      </Card>

      {attachments.length > 0 && (
        <Card>
          <CardHeader><CardTitle>Attachments ({attachments.length})</CardTitle></CardHeader>
          <CardContent className="divide-y divide-border p-0">
            {attachments.map((att) => (
              <div key={att.id} className="flex items-center justify-between gap-3 px-6 py-3 text-sm">
                <div className="min-w-0">
                  <div className="truncate font-mono text-xs">{att.name}</div>
                  <div className="text-xs text-muted-foreground">
                    {att.contentType} · {Math.round(att.size / 1024)} KB
                  </div>
                </div>
                <a
                  href={`/api/inbox/gmail/${encodeURIComponent(id)}/attachments/${encodeURIComponent(att.id)}`}
                  className="text-xs underline underline-offset-4"
                  download={att.name}
                >
                  Download
                </a>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle>Body</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          {isHtml ? (
            <iframe
              src={`/api/inbox/gmail/${encodeURIComponent(id)}/html`}
              className="h-[600px] w-full rounded-md border border-border bg-background"
              sandbox="allow-same-origin"
              title={subject}
            />
          ) : textBody?.trim() ? (
            <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-md border border-border bg-muted/30 p-3 font-mono text-xs leading-relaxed">
              {textBody}
            </pre>
          ) : (
            <p className="text-sm text-muted-foreground">Empty body.</p>
          )}
          {isHtml && msg.snippet && (
            <>
              <Separator />
              <div>
                <div className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">Preview</div>
                <p className="text-xs text-muted-foreground">{msg.snippet}</p>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

async function renderOutlookMessage(id: string) {
  const resolved = await resolveGraphToken();
  if (!resolved) notFound();

  const msgPath = `${resolved.userPath}/messages/${encodeURIComponent(id)}`;

  let message: OutlookMessage;
  let attachments: OutlookAttachmentMeta[] = [];
  try {
    message = await graphJsonAuto<OutlookMessage>(msgPath);
    if (message.hasAttachments) {
      const attJson = await graphJsonAuto<{ value: OutlookAttachmentMeta[] }>(
        `${msgPath}/attachments?$select=id,name,contentType,size,isInline,contentId`,
      );
      attachments = attJson.value;
    }
  } catch {
    notFound();
  }

  const formId = extractFormId(message.subject);
  const incident = await findIncidentByFormId(formId);
  const isHtml = message.body?.contentType === "html" && Boolean(message.body.content?.trim());
  const analysis = await getExistingAnalysis("outlook_email" as SourceType, id);
  const analysisProps = analysis?.pipeline_status ? {
    label: analysis.classification_label ?? "unknown",
    confidence: analysis.classification_confidence ?? 0,
    reason: analysis.classification_reason ?? "",
    incidentFormId: analysis.incident_form_id,
    pipelineStatus: analysis.pipeline_status,
    errorMessage: analysis.error_message,
  } : null;

  const savedEmail = await prisma.emailMessage.findFirst({
    where: { messageIdHeader: message.internetMessageId ?? id },
    select: { id: true },
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h1 className="text-2xl font-medium tracking-tight">{message.subject || "(no subject)"}</h1>
          <p className="text-xs text-muted-foreground">{formatDateTime(message.receivedDateTime)}</p>
          {message.importance === "high" && (
            <Badge variant="solid" className="mt-1">high importance</Badge>
          )}
        </div>
        <div className="flex items-center gap-3">
          <SaveEmailButton messageId={id} provider="microsoft" alreadySaved={!!savedEmail} />
          {message.webLink && (
            <a
              href={message.webLink}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-muted-foreground underline underline-offset-4 hover:text-foreground"
            >
              Open in Outlook
            </a>
          )}
          <Link href="/inbox/outlook" className="text-sm text-muted-foreground hover:text-foreground">
            ← Back
          </Link>
        </div>
      </div>

      {(incident || formId) && (
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
            {formId && <span className="font-mono text-xs text-muted-foreground">{formId}</span>}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle>AI Analysis</CardTitle></CardHeader>
        <CardContent>
          <EmailAnalyzeWrapper messageId={id} provider="microsoft" existingAnalysis={analysisProps} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Headers</CardTitle></CardHeader>
        <CardContent className="space-y-2 text-sm">
          <Row label="From">
            <span className="inline-flex items-center gap-1.5 font-mono text-xs">
              {message.from?.emailAddress?.address ?? "—"}
              {message.from?.emailAddress?.address && <CopyButton value={message.from.emailAddress.address} />}
            </span>
            {message.from?.emailAddress?.name && (
              <span className="ml-2 text-muted-foreground">{message.from.emailAddress.name}</span>
            )}
          </Row>
          <Row label="To">
            <span className="font-mono text-xs">{flattenAddresses(message.toRecipients) || "—"}</span>
          </Row>
          {message.ccRecipients && message.ccRecipients.length > 0 && (
            <Row label="CC"><span className="font-mono text-xs">{flattenAddresses(message.ccRecipients)}</span></Row>
          )}
          {message.bccRecipients && message.bccRecipients.length > 0 && (
            <Row label="BCC"><span className="font-mono text-xs">{flattenAddresses(message.bccRecipients)}</span></Row>
          )}
          {message.replyTo && message.replyTo.length > 0 && (
            <Row label="Reply-To"><span className="font-mono text-xs">{flattenAddresses(message.replyTo)}</span></Row>
          )}
          {message.internetMessageId && (
            <Row label="Message-ID"><span className="font-mono text-xs">{message.internetMessageId}</span></Row>
          )}
          <Row label="Read">{message.isRead ? "Yes" : "No"}</Row>
        </CardContent>
      </Card>

      {attachments.length > 0 && (
        <Card>
          <CardHeader><CardTitle>Attachments ({attachments.length})</CardTitle></CardHeader>
          <CardContent className="divide-y divide-border p-0">
            {attachments.map((att) => {
              const isImage = att.contentType.startsWith("image/") && !att.isInline;
              const proxyUrl = `/api/inbox/outlook/${encodeURIComponent(message.id)}/attachments/${encodeURIComponent(att.id)}`;
              return (
                <div key={att.id} className="flex items-center justify-between gap-3 px-6 py-3 text-sm">
                  <div className="flex items-center gap-3 min-w-0">
                    {isImage && (
                      /* eslint-disable-next-line @next/next/no-img-element */
                      <img
                        src={proxyUrl}
                        alt={att.name}
                        className="h-12 w-12 shrink-0 rounded object-cover border border-border"
                        loading="lazy"
                      />
                    )}
                    <div className="min-w-0">
                      <div className="truncate font-mono text-xs">{att.name}</div>
                      <div className="text-xs text-muted-foreground">
                        {att.contentType} · {Math.round(att.size / 1024)} KB
                        {att.isInline ? " · inline" : null}
                      </div>
                    </div>
                  </div>
                  <a
                    href={proxyUrl}
                    className="text-xs underline underline-offset-4"
                    download={att.name}
                  >
                    Download
                  </a>
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle>Body</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          {isHtml ? (
            <iframe
              src={`/api/inbox/outlook/${encodeURIComponent(message.id)}/html`}
              className="h-[600px] w-full rounded-md border border-border bg-background"
              sandbox="allow-same-origin"
              title={message.subject || "Email body"}
            />
          ) : message.body?.content?.trim() ? (
            <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-md border border-border bg-muted/30 p-3 font-mono text-xs leading-relaxed">
              {message.body.content}
            </pre>
          ) : (
            <p className="text-sm text-muted-foreground">Empty body.</p>
          )}
          {isHtml && message.bodyPreview && (
            <>
              <Separator />
              <div>
                <div className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">Preview</div>
                <p className="text-xs text-muted-foreground">{message.bodyPreview}</p>
              </div>
            </>
          )}
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
