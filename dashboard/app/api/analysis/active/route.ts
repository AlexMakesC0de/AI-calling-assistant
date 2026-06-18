import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { prisma } from "@/lib/prisma";

type ActiveAnalysis = {
  sourceType: string;
  sourceId: string;
  pipelineStatus: string;
  pipelineStep: string | null;
  contentPreview: string | null;
  sender: string | null;
  classificationLabel: string | null;
  incidentFormId: number | null;
};

export async function GET() {
  const session = await getSession();
  if (!session) return NextResponse.json({ error: "Not authenticated" }, { status: 401 });

  const rows = await prisma.$queryRaw<ActiveAnalysis[]>`
    SELECT source_type as "sourceType", source_id as "sourceId",
           pipeline_status as "pipelineStatus", pipeline_step as "pipelineStep",
           content_preview as "contentPreview", sender,
           classification_label as "classificationLabel",
           incident_form_id as "incidentFormId"
    FROM content_analysis
    WHERE account_id = ${session.accountId}
      AND (
        pipeline_status = 'pending'
        OR (pipeline_status IN ('completed', 'failed') AND analyzed_at > NOW() - INTERVAL '30 seconds')
      )
    ORDER BY analyzed_at DESC
    LIMIT 20
  `;

  return NextResponse.json(rows);
}
