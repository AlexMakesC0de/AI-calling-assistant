import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { getAnalysisStatus, type SourceType } from "@/lib/analyze-content";
import { prisma } from "@/lib/prisma";

export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session) return NextResponse.json({ error: "Not authenticated" }, { status: 401 });

  const sourceType = req.nextUrl.searchParams.get("sourceType") as SourceType | null;
  const sourceId = req.nextUrl.searchParams.get("sourceId");
  const sourceIds = req.nextUrl.searchParams.get("sourceIds");

  if (!sourceType) {
    return NextResponse.json({ error: "Missing sourceType" }, { status: 400 });
  }

  if (sourceIds) {
    const ids = sourceIds.split(",").filter(Boolean);
    if (ids.length === 0) return NextResponse.json([]);

    const rows = await prisma.$queryRaw<
      { source_id: string; pipeline_status: string; pipeline_step: string | null; classification_label: string | null; classification_confidence: number | null; classification_reason: string | null; incident_form_id: number | null; error_message: string | null }[]
    >`
      SELECT source_id, pipeline_status, pipeline_step, classification_label, classification_confidence,
             classification_reason, incident_form_id, error_message
      FROM content_analysis
      WHERE source_type = ${sourceType} AND source_id = ANY(${ids})
    `;

    const results = ids.map((id) => {
      const r = rows.find((row) => row.source_id === id);
      if (!r) return { sourceId: id, pipelineStatus: "not_found", pipelineStep: null, classificationLabel: null, classificationConfidence: null, classificationReason: null, incidentFormId: null, errorMessage: null };
      return {
        sourceId: id,
        pipelineStatus: r.pipeline_status,
        pipelineStep: r.pipeline_step,
        classificationLabel: r.classification_label,
        classificationConfidence: r.classification_confidence,
        classificationReason: r.classification_reason,
        incidentFormId: r.incident_form_id,
        errorMessage: r.error_message,
      };
    });
    return NextResponse.json(results);
  }

  if (!sourceId) {
    return NextResponse.json({ error: "Missing sourceId or sourceIds" }, { status: 400 });
  }

  const status = await getAnalysisStatus(sourceType, sourceId);
  return NextResponse.json(status ?? { pipelineStatus: "not_found" });
}
