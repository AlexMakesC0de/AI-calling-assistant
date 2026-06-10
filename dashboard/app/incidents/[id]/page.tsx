import Link from "next/link";
import { notFound } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { JsonTree } from "@/components/json-tree";
import { prisma } from "@/lib/prisma";
import { asFormData, sentimentTone, stepsToList } from "@/lib/incident-form";
import { searchMailpitMessages, type MailpitMessageSummary } from "@/lib/mailpit";
import { formatDateTime } from "@/lib/utils";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";

async function findEmailForFormId(formId: string | null | undefined): Promise<MailpitMessageSummary | null> {
  if (!formId) return null;
  try {
    const result = await searchMailpitMessages(`subject:"${formId}"`, 1);
    return result.messages[0] ?? null;
  } catch {
    return null;
  }
}

export default async function IncidentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const numericId = Number(id);
  if (!Number.isFinite(numericId)) notFound();

  const incident = await prisma.incidentForm.findUnique({
    where: { id: numericId },
    include: {
      generalInformation: true,
      transcriptions: { orderBy: { createdAt: "asc" } },
    },
  });
  if (!incident) notFound();

  const data = asFormData(incident.generalInformation?.formData);
  const original = incident.transcriptions.find((t) => t.langCode !== "nl");
  const dutch = incident.transcriptions.find((t) => t.langCode === "nl");
  const dispatchedEmail = await findEmailForFormId(data.form_id);

  const sentiment = original?.sentiment ?? data.customer_sentiment ?? null;
  const tone = sentimentTone(sentiment);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h1 className="text-2xl font-medium tracking-tight">Incident #{incident.id}</h1>
          {data.form_id ? <p className="font-mono text-xs text-muted-foreground">{data.form_id}</p> : null}
        </div>
        <div className="flex items-center gap-2">
          <Button asChild variant="outline">
            <a href={`/api/incidents/${incident.id}/docx`} download>
              Download Word
            </a>
          </Button>
          <Link href="/incidents" className="text-sm text-muted-foreground hover:text-foreground">
            ← Back to incidents
          </Link>
        </div>
      </div>

      {dispatchedEmail ? (
        <Card>
          <CardContent className="flex items-center justify-between py-3 text-sm">
            <div>
              <span className="text-muted-foreground">Dispatched email:</span>{" "}
              <Link
                href={`/inbox/${encodeURIComponent(dispatchedEmail.ID)}`}
                className="underline underline-offset-4"
              >
                {dispatchedEmail.Subject || "(no subject)"}
              </Link>
              <span className="ml-2 text-xs text-muted-foreground">
                to {dispatchedEmail.To.map((t) => t.Address).join(", ")}
              </span>
            </div>
            <span className="text-xs text-muted-foreground">{formatDateTime(dispatchedEmail.Created)}</span>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Overview</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-6 md:grid-cols-4">
          <Field label="Completed">{formatDateTime(incident.completedAt)}</Field>
          <Field label="Status">{incident.status}</Field>
          <Field label="Category">{incident.category ?? "—"}</Field>
          <Field label="Priority">
            {incident.priority ? <Badge variant="solid">{incident.priority}</Badge> : "—"}
          </Field>
          <Field label="Sentiment">
            <span
              className={cn(
                "rounded-md border px-2 py-0.5 text-xs",
                tone === "negative" && "border-foreground bg-foreground text-background",
                tone !== "negative" && "border-border"
              )}
            >
              {sentiment ?? "—"}
            </span>
          </Field>
          <Field label="Caller">{incident.generalInformation?.callerName ?? "—"}</Field>
          <Field label="Agent">{incident.generalInformation?.agentName ?? "—"}</Field>
          <Field label="Audio file">
            {incident.generalInformation?.audioFilename ? (
              <span className="font-mono text-xs">{incident.generalInformation.audioFilename}</span>
            ) : (
              "—"
            )}
          </Field>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Caller</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Row label="Name">{data.caller_information?.name ?? "—"}</Row>
            <Row label="Account">{data.caller_information?.account_or_reference ?? "—"}</Row>
            <Row label="Contact">{data.caller_information?.contact_info ?? "—"}</Row>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Issue</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Row label="Category">{data.issue?.category ?? "—"}</Row>
            <Row label="Priority">{data.issue?.priority ?? "—"}</Row>
            <Row label="Description">{data.issue?.description ?? "—"}</Row>
            <Row label="Errors">{data.issue?.error_messages ?? "—"}</Row>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Resolution</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Row label="Status">{data.resolution?.status ?? "—"}</Row>
            <Row label="Outcome">{data.resolution?.outcome ?? "—"}</Row>
            <div className="space-y-1">
              <div className="text-xs uppercase tracking-wide text-muted-foreground">Steps taken</div>
              {stepsToList(data.resolution?.steps_taken).length > 0 ? (
                <ol className="ml-4 list-decimal space-y-1">
                  {stepsToList(data.resolution?.steps_taken).map((step, idx) => (
                    <li key={idx}>{step}</li>
                  ))}
                </ol>
              ) : (
                <span className="text-muted-foreground">None recorded.</span>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Follow-up</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Row label="Required">{data.follow_up?.required ? "Yes" : "No"}</Row>
            <Row label="Department">{data.follow_up?.department ?? "—"}</Row>
            <div className="space-y-1">
              <div className="text-xs uppercase tracking-wide text-muted-foreground">Actions</div>
              {stepsToList(data.follow_up?.actions).length > 0 ? (
                <ul className="ml-4 list-disc space-y-1">
                  {stepsToList(data.follow_up?.actions).map((step, idx) => (
                    <li key={idx}>{step}</li>
                  ))}
                </ul>
              ) : (
                <span className="text-muted-foreground">None.</span>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Summary</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <p>{data.call_summary || original?.summary || "No summary recorded."}</p>
          {dutch?.summary ? (
            <>
              <Separator />
              <div className="space-y-1">
                <div className="text-xs uppercase tracking-wide text-muted-foreground">Nederlands</div>
                <p>{dutch.summary}</p>
              </div>
            </>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Transcript</CardTitle>
        </CardHeader>
        <CardContent>
          {original?.transcriptText ? (
            <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-md border border-border bg-muted/30 p-3 font-mono text-xs leading-relaxed">
              {original.transcriptText}
            </pre>
          ) : (
            <p className="text-sm text-muted-foreground">No transcript stored.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Form data</CardTitle>
        </CardHeader>
        <CardContent>
          <JsonTree value={data} rootName="form_data" defaultOpenDepth={2} />
        </CardContent>
      </Card>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="text-sm">{children}</div>
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
