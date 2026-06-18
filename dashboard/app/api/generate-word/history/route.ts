import { NextResponse } from "next/server";
import { Document, HeadingLevel, Packer, Paragraph, TextRun } from "docx";
import { Prisma } from "@prisma/client";
import { prisma } from "@/lib/prisma";
import { asFormData, stepsToList } from "@/lib/incident-form";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const heading = (text: string, level: (typeof HeadingLevel)[keyof typeof HeadingLevel] = HeadingLevel.HEADING_2) =>
  new Paragraph({ text, heading: level, spacing: { before: 300, after: 120 } });

const kv = (label: string, value: string | undefined | null) =>
  new Paragraph({
    children: [
      new TextRun({ text: `${label}: `, bold: true, size: 20 }),
      new TextRun({ text: value?.trim() || "—", size: 20 }),
    ],
    spacing: { after: 60 },
  });

const body = (text: string) =>
  new Paragraph({ text, spacing: { after: 60 }, style: "Normal" });

const divider = () =>
  new Paragraph({
    children: [new TextRun({ text: "─".repeat(60), color: "CCCCCC", size: 16 })],
    spacing: { before: 300, after: 300 },
  });

function formatDate(date: Date): string {
  return date.toLocaleDateString("en-IE", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

type TimelineEntry = {
  date: Date;
  channel: "call" | "whatsapp" | "email";
  render: () => Paragraph[];
};

export async function POST(request: Request) {
  const json = await request.json();
  const incidentIds: number[] = json.incidentIds ?? [];
  const whatsappIds: number[] = json.whatsappIds ?? [];
  const emailIds: number[] = json.emailIds ?? [];

  if (incidentIds.length + whatsappIds.length + emailIds.length === 0) {
    return NextResponse.json({ error: "No items selected" }, { status: 400 });
  }

  const timeline: TimelineEntry[] = [];

  // Fetch incidents
  if (incidentIds.length > 0) {
    const incidents = await prisma.incidentForm.findMany({
      where: { id: { in: incidentIds } },
      include: {
        generalInformation: true,
        transcriptions: { orderBy: { createdAt: "asc" } },
      },
    });

    for (const inc of incidents) {
      const data = asFormData(inc.generalInformation?.formData);
      const original = inc.transcriptions.find((t) => t.langCode !== "nl");

      timeline.push({
        date: inc.completedAt,
        channel: "call",
        render: () => {
          const paragraphs: Paragraph[] = [
            heading(`Call — ${inc.generalInformation?.callerName || `Incident #${inc.id}`}`, HeadingLevel.HEADING_3),
            kv("Date", formatDate(inc.completedAt)),
            kv("Category", inc.category),
            kv("Priority", inc.priority),
            kv("Agent", inc.generalInformation?.agentName),
            kv("Account", data.caller_information?.account_or_reference),
            kv("Sentiment", original?.sentiment ?? data.customer_sentiment),
          ];

          if (data.issue?.description) {
            paragraphs.push(
              new Paragraph({
                children: [new TextRun({ text: "Issue:", bold: true, size: 20 })],
                spacing: { before: 80 },
              }),
              body(data.issue.description),
            );
          }

          const summary = data.call_summary || original?.summary;
          if (summary) {
            paragraphs.push(
              new Paragraph({
                children: [new TextRun({ text: "Summary:", bold: true, size: 20 })],
                spacing: { before: 80 },
              }),
              body(summary),
            );
          }

          const steps = stepsToList(data.resolution?.steps_taken);
          if (steps.length > 0 || data.resolution?.status) {
            paragraphs.push(
              new Paragraph({
                children: [new TextRun({ text: "Resolution:", bold: true, size: 20 })],
                spacing: { before: 80 },
              }),
            );
            if (data.resolution?.status) paragraphs.push(kv("Status", data.resolution.status));
            if (data.resolution?.outcome) paragraphs.push(kv("Outcome", data.resolution.outcome));
            for (const step of steps) {
              paragraphs.push(new Paragraph({ text: step, bullet: { level: 0 }, spacing: { after: 40 } }));
            }
          }

          if (data.follow_up?.required) {
            paragraphs.push(
              new Paragraph({
                children: [new TextRun({ text: "Follow-up:", bold: true, size: 20 })],
                spacing: { before: 80 },
              }),
            );
            if (data.follow_up.department) paragraphs.push(kv("Department", data.follow_up.department));
            for (const action of stepsToList(data.follow_up.actions)) {
              paragraphs.push(new Paragraph({ text: action, bullet: { level: 0 }, spacing: { after: 40 } }));
            }
          }

          if (original?.transcriptText) {
            paragraphs.push(
              new Paragraph({
                children: [new TextRun({ text: "Transcript:", bold: true, size: 20 })],
                spacing: { before: 80 },
              }),
            );
            for (const line of original.transcriptText.split(/\n+/)) {
              if (line.trim()) {
                paragraphs.push(new Paragraph({
                  children: [new TextRun({ text: line, size: 18, font: "Consolas" })],
                  spacing: { after: 20 },
                }));
              }
            }
          }

          return paragraphs;
        },
      });
    }
  }

  // Fetch WhatsApp conversations
  if (whatsappIds.length > 0) {
    const conversations = await prisma.whatsAppConversation.findMany({
      where: { id: { in: whatsappIds } },
      include: {
        messages: { orderBy: { createdAt: "asc" } },
      },
    });

    for (const conv of conversations) {
      const firstMsg = conv.messages[0];
      if (!firstMsg) continue;

      timeline.push({
        date: firstMsg.createdAt,
        channel: "whatsapp",
        render: () => {
          const paragraphs: Paragraph[] = [
            heading(`WhatsApp — ${conv.contactName || conv.contactPhone}`, HeadingLevel.HEADING_3),
            kv("Contact", conv.contactPhone),
            ...(conv.contactName ? [kv("Name", conv.contactName)] : []),
            kv("Messages", String(conv.messages.length)),
            new Paragraph({ text: "", spacing: { after: 40 } }),
          ];

          for (const msg of conv.messages) {
            const sender = msg.direction === "inbound"
              ? (conv.contactName || conv.contactPhone)
              : "Repak Support";
            const time = formatDate(msg.createdAt);
            const content = msg.messageType !== "text"
              ? `[${msg.messageType.replace("_", " ")}]`
              : (msg.body || "");

            paragraphs.push(new Paragraph({
              children: [
                new TextRun({ text: `[${time}] `, color: "888888", size: 18 }),
                new TextRun({ text: `${sender}: `, bold: true, size: 20 }),
                new TextRun({ text: content, size: 20 }),
              ],
              spacing: { after: 40 },
            }));
          }

          return paragraphs;
        },
      });
    }
  }

  // Fetch email conversations via raw query (Prisma client may not have this model yet)
  if (emailIds.length > 0) {
    type RawConv = { id: number; sender_email: string; sender_name: string | null };
    type RawMsg = {
      id: number; conversation_id: number; direction: string; subject: string | null;
      from_email: string; from_name: string | null; to_email: string | null;
      body_text: string | null; created_at: Date;
    };

    const convRows = await prisma.$queryRaw<RawConv[]>`
      SELECT id, sender_email, sender_name FROM email_conversation WHERE id IN (${Prisma.join(emailIds)})
    `;
    const msgRows = await prisma.$queryRaw<RawMsg[]>`
      SELECT id, conversation_id, direction, subject, from_email, from_name, to_email, body_text, created_at
      FROM email_message WHERE conversation_id IN (${Prisma.join(emailIds)}) ORDER BY created_at ASC
    `;

    for (const conv of convRows) {
      const messages = msgRows.filter((m) => m.conversation_id === conv.id);
      const firstMsg = messages[0];
      if (!firstMsg) continue;

      timeline.push({
        date: firstMsg.created_at,
        channel: "email",
        render: () => {
          const paragraphs: Paragraph[] = [
            heading(`Email — ${conv.sender_name || conv.sender_email}`, HeadingLevel.HEADING_3),
            kv("Contact", conv.sender_email),
          ];

          for (const msg of messages) {
            paragraphs.push(
              new Paragraph({
                children: [
                  new TextRun({ text: formatDate(msg.created_at), color: "888888", size: 18 }),
                ],
                spacing: { before: 120, after: 40 },
              }),
              kv("From", msg.from_name ? `${msg.from_name} <${msg.from_email}>` : msg.from_email),
              kv("To", msg.to_email),
              kv("Subject", msg.subject),
            );

            if (msg.body_text) {
              paragraphs.push(new Paragraph({ text: "", spacing: { after: 20 } }));
              for (const line of msg.body_text.split(/\n/)) {
                paragraphs.push(new Paragraph({
                  children: [new TextRun({ text: line, size: 20 })],
                  spacing: { after: 20 },
                }));
              }
            }
          }

          return paragraphs;
        },
      });
    }
  }

  // Sort chronologically
  timeline.sort((a, b) => a.date.getTime() - b.date.getTime());

  // Build document
  const children: Paragraph[] = [
    new Paragraph({
      text: "Issue History Report",
      heading: HeadingLevel.TITLE,
    }),
    new Paragraph({
      children: [
        new TextRun({
          text: `Generated ${formatDate(new Date())} · ${timeline.length} item${timeline.length === 1 ? "" : "s"}`,
          color: "666666",
          size: 20,
        }),
      ],
      spacing: { after: 300 },
    }),
  ];

  for (let i = 0; i < timeline.length; i++) {
    if (i > 0) children.push(divider());
    const channelLabel = { call: "Phone Call", whatsapp: "WhatsApp", email: "Email" }[timeline[i].channel];
    children.push(new Paragraph({
      children: [new TextRun({ text: channelLabel.toUpperCase(), bold: true, size: 16, color: "999999" })],
      spacing: { after: 0 },
    }));
    children.push(...timeline[i].render());
  }

  const doc = new Document({ sections: [{ children }] });
  const buffer = await Packer.toBuffer(doc);
  const bytes = new Uint8Array(buffer);

  const filename = `issue-history-${new Date().toISOString().slice(0, 10)}.docx`;
  return new NextResponse(bytes, {
    status: 200,
    headers: {
      "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "Content-Disposition": `attachment; filename="${filename}"`,
      "Content-Length": String(bytes.byteLength),
      "Cache-Control": "no-store",
    },
  });
}
