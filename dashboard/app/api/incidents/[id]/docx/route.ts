import { NextResponse } from "next/server";
import { Document, HeadingLevel, Packer, Paragraph, TextRun } from "docx";
import { prisma } from "@/lib/prisma";
import { asFormData, stepsToList } from "@/lib/incident-form";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const numericId = Number(id);
  if (!Number.isFinite(numericId)) return new NextResponse("Bad id", { status: 400 });

  const incident = await prisma.incidentForm.findUnique({
    where: { id: numericId },
    include: {
      generalInformation: true,
      transcriptions: { orderBy: { createdAt: "asc" } },
    },
  });
  if (!incident) return new NextResponse("Not found", { status: 404 });

  const data = asFormData(incident.generalInformation?.formData);
  const original = incident.transcriptions.find((t) => t.langCode !== "nl");
  const dutch = incident.transcriptions.find((t) => t.langCode === "nl");

  const heading = (text: string, level: typeof HeadingLevel[keyof typeof HeadingLevel] = HeadingLevel.HEADING_2) =>
    new Paragraph({ text, heading: level, spacing: { before: 240, after: 120 } });

  const kv = (label: string, value: string | undefined | null) =>
    new Paragraph({
      children: [
        new TextRun({ text: `${label}: `, bold: true }),
        new TextRun({ text: value && value.trim() ? value : "—" }),
      ],
      spacing: { after: 60 },
    });

  const bullet = (text: string) =>
    new Paragraph({ text, bullet: { level: 0 }, spacing: { after: 40 } });

  const subtitle = `${incident.category ?? "Uncategorized"}${
    incident.priority ? ` · ${incident.priority}` : ""
  }${data.form_id ? ` · ${data.form_id}` : ""}`;

  const children: Paragraph[] = [
    new Paragraph({
      text: `Incident #${incident.id}`,
      heading: HeadingLevel.TITLE,
    }),
    new Paragraph({
      children: [new TextRun({ text: subtitle, color: "666666" })],
      spacing: { after: 240 },
    }),

    heading("Overview"),
    kv("Completed", incident.completedAt.toISOString()),
    kv("Status", incident.status),
    kv("Caller", incident.generalInformation?.callerName),
    kv("Agent", incident.generalInformation?.agentName),
    kv("Audio file", incident.generalInformation?.audioFilename),
    kv(
      "Sentiment",
      original?.sentiment ?? data.customer_sentiment ?? null
    ),

    heading("Caller information"),
    kv("Name", data.caller_information?.name),
    kv("Account / reference", data.caller_information?.account_or_reference),
    kv("Contact", data.caller_information?.contact_info),

    heading("Issue"),
    kv("Category", data.issue?.category),
    kv("Priority", data.issue?.priority),
    kv("Description", data.issue?.description),
    kv("Errors", data.issue?.error_messages),

    heading("Resolution"),
    kv("Status", data.resolution?.status),
    kv("Outcome", data.resolution?.outcome),
  ];

  const steps = stepsToList(data.resolution?.steps_taken);
  if (steps.length > 0) {
    children.push(new Paragraph({ children: [new TextRun({ text: "Steps taken:", bold: true })] }));
    for (const step of steps) children.push(bullet(step));
  }

  children.push(heading("Follow-up"));
  children.push(kv("Required", data.follow_up?.required ? "Yes" : "No"));
  children.push(kv("Department", data.follow_up?.department));
  const actions = stepsToList(data.follow_up?.actions);
  if (actions.length > 0) {
    children.push(new Paragraph({ children: [new TextRun({ text: "Actions:", bold: true })] }));
    for (const action of actions) children.push(bullet(action));
  }

  children.push(heading("Summary"));
  children.push(
    new Paragraph({ text: data.call_summary || original?.summary || "No summary recorded.", spacing: { after: 120 } })
  );
  if (dutch?.summary) {
    children.push(new Paragraph({ children: [new TextRun({ text: "Nederlands:", bold: true })] }));
    children.push(new Paragraph({ text: dutch.summary, spacing: { after: 120 } }));
  }

  if (original?.transcriptText) {
    children.push(heading("Transcript"));
    for (const line of original.transcriptText.split(/\n+/)) {
      if (line.trim()) children.push(new Paragraph({ text: line, spacing: { after: 40 } }));
    }
  }

  const doc = new Document({ sections: [{ children }] });
  const buffer = await Packer.toBuffer(doc);
  // Wrap in a fresh Uint8Array so the response body type matches BodyInit.
  const body = new Uint8Array(buffer);

  const filename = `incident-${incident.id}${data.form_id ? `-${data.form_id}` : ""}.docx`;
  return new NextResponse(body, {
    status: 200,
    headers: {
      "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "Content-Disposition": `attachment; filename="${filename}"`,
      "Content-Length": String(body.byteLength),
      "Cache-Control": "no-store",
    },
  });
}
