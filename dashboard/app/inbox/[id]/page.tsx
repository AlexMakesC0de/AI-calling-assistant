import Link from "next/link";
import { notFound } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { prisma } from "@/lib/prisma";
import { getMailpitMessage, type MailpitMessage } from "@/lib/mailpit";
import { formatDateTime } from "@/lib/utils";

export const dynamic = "force-dynamic";

// Subjects look like:  "Incident Form Completed - <form_id> [<category>]"
// Pull the form_id out so we can deep-link back to the matching incident.
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

export default async function MessagePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let message: MailpitMessage;
  try {
    message = await getMailpitMessage(id);
  } catch {
    notFound();
  }

  const formId = extractFormId(message.Subject);
  const incident = await findIncidentByFormId(formId);

  const hasHtml = Boolean(message.HTML?.trim());
  const attachments = message.Attachments ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h1 className="text-2xl font-medium tracking-tight">{message.Subject || "(no subject)"}</h1>
          <p className="text-xs text-muted-foreground">{formatDateTime(message.Date)}</p>
          {message.Tags && message.Tags.length > 0 ? (
            <div className="flex flex-wrap gap-1.5 pt-1">
              {message.Tags.map((tag) => (
                <Badge key={tag} variant="muted">
                  {tag}
                </Badge>
              ))}
            </div>
          ) : null}
        </div>
        <Link href="/inbox" className="text-sm text-muted-foreground hover:text-foreground">
          ← Back to inbox
        </Link>
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
            <span className="font-mono text-xs">{message.From.Address}</span>
            {message.From.Name ? <span className="ml-2 text-muted-foreground">{message.From.Name}</span> : null}
          </Row>
          <Row label="To">
            <span className="font-mono text-xs">{message.To.map((t) => t.Address).join(", ") || "—"}</span>
          </Row>
          {message.Cc && message.Cc.length > 0 ? (
            <Row label="CC">
              <span className="font-mono text-xs">{message.Cc.map((t) => t.Address).join(", ")}</span>
            </Row>
          ) : null}
          {message.Bcc && message.Bcc.length > 0 ? (
            <Row label="BCC">
              <span className="font-mono text-xs">{message.Bcc.map((t) => t.Address).join(", ")}</span>
            </Row>
          ) : null}
          {message.ReplyTo && message.ReplyTo.length > 0 ? (
            <Row label="Reply-To">
              <span className="font-mono text-xs">{message.ReplyTo.map((t) => t.Address).join(", ")}</span>
            </Row>
          ) : null}
          <Row label="Size">{Math.round(message.Size / 1024)} KB</Row>
          <Row label="Message-ID">
            <span className="font-mono text-xs">{message.MessageID}</span>
          </Row>
          <Row label="Source">
            <a
              href={`/api/inbox/${encodeURIComponent(message.ID)}/raw`}
              className="text-xs underline underline-offset-4"
              download={`${message.ID}.eml`}
            >
              Download raw .eml
            </a>
          </Row>
        </CardContent>
      </Card>

      {attachments.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Attachments ({attachments.length})</CardTitle>
          </CardHeader>
          <CardContent className="divide-y divide-border p-0">
            {attachments.map((att) => (
              <div key={att.PartID} className="flex items-center justify-between gap-3 px-6 py-3 text-sm">
                <div className="min-w-0">
                  <div className="truncate font-mono text-xs">{att.FileName}</div>
                  <div className="text-xs text-muted-foreground">
                    {att.ContentType} · {Math.round(att.Size / 1024)} KB
                  </div>
                </div>
                <a
                  href={`/api/inbox/${encodeURIComponent(message.ID)}/part/${encodeURIComponent(att.PartID)}`}
                  className="text-xs underline underline-offset-4"
                  download={att.FileName}
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
          {hasHtml ? (
            <iframe
              src={`/api/inbox/${encodeURIComponent(message.ID)}/html`}
              className="h-[600px] w-full rounded-md border border-border bg-background"
              sandbox="allow-same-origin"
              title={message.Subject || "Email body"}
            />
          ) : null}
          {message.Text?.trim() ? (
            <>
              {hasHtml ? <Separator /> : null}
              <div>
                <div className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">Plain text</div>
                <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-md border border-border bg-muted/30 p-3 font-mono text-xs leading-relaxed">
                  {message.Text}
                </pre>
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
