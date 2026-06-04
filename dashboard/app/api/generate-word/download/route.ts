import { NextResponse } from "next/server";
import { readFileSync } from "fs";
import { join } from "path";
import PizZip from "pizzip";
import Docxtemplater from "docxtemplater";
import type { IncidentFormData } from "@/lib/incident-form";
import { stepsToList } from "@/lib/incident-form";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function flattenFormData(data: IncidentFormData): Record<string, string> {
  const flat: Record<string, string> = {};

  flat["form_id"] = data.form_id ?? "";
  flat["completed_at"] = data.completed_at ?? "";
  flat["call_summary"] = data.call_summary ?? "";
  flat["customer_sentiment"] = data.customer_sentiment ?? "";

  flat["caller_information.name"] = data.caller_information?.name ?? "";
  flat["caller_information.account_or_reference"] = data.caller_information?.account_or_reference ?? "";
  flat["caller_information.contact_info"] = data.caller_information?.contact_info ?? "";

  flat["call_details.date"] = data.call_details?.date ?? "";
  flat["call_details.duration_estimate"] = data.call_details?.duration_estimate ?? "";
  flat["call_details.agent_name"] = data.call_details?.agent_name ?? "";

  flat["issue.category"] = data.issue?.category ?? "";
  flat["issue.priority"] = data.issue?.priority ?? "";
  flat["issue.description"] = data.issue?.description ?? "";
  flat["issue.error_messages"] = data.issue?.error_messages ?? "";

  flat["resolution.status"] = data.resolution?.status ?? "";
  flat["resolution.steps_taken"] = stepsToList(data.resolution?.steps_taken).join("; ");
  flat["resolution.outcome"] = data.resolution?.outcome ?? "";

  flat["follow_up.required"] = data.follow_up?.required ? "Yes" : "No";
  flat["follow_up.actions"] = stepsToList(data.follow_up?.actions).join("; ");
  flat["follow_up.department"] = data.follow_up?.department ?? "";

  flat["transcript.full_text"] = data.transcript?.full_text ?? "";
  flat["transcript.word_count"] = data.transcript?.word_count?.toString() ?? "";

  return flat;
}

function resolveTemplatePath(): string {
  const candidates = [
    join(process.cwd(), "templates", "incident_form_template_with_tokens.docx"),
    join(process.cwd(), "..", "templates", "incident_form_template_with_tokens.docx"),
  ];
  if (process.env.TEMPLATE_DIR) {
    candidates.unshift(
      join(process.env.TEMPLATE_DIR, "incident_form_template_with_tokens.docx"),
    );
  }
  for (const p of candidates) {
    try {
      readFileSync(p);
      return p;
    } catch {
      continue;
    }
  }
  throw new Error(
    `Template not found. Searched: ${candidates.join(", ")}`,
  );
}

export async function POST(request: Request) {
  const formData: IncidentFormData = await request.json();

  let templatePath: string;
  try {
    templatePath = resolveTemplatePath();
  } catch (e) {
    return NextResponse.json(
      { error: (e as Error).message },
      { status: 500 },
    );
  }

  const templateBuf = readFileSync(templatePath);
  const zip = new PizZip(templateBuf);
  const doc = new Docxtemplater(zip, {
    paragraphLoop: false,
    linebreaks: true,
    delimiters: { start: "{", end: "}" },
  });

  const flat = flattenFormData(formData);
  doc.render(flat);

  const buf = doc.getZip().generate({ type: "nodebuffer" });
  const body = new Uint8Array(buf);
  const filename = `incident-${formData.form_id ?? "report"}.docx`;

  return new NextResponse(body, {
    status: 200,
    headers: {
      "Content-Type":
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "Content-Disposition": `attachment; filename="${filename}"`,
      "Content-Length": String(body.byteLength),
      "Cache-Control": "no-store",
    },
  });
}
