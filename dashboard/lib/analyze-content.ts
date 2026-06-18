import { prisma } from "./prisma";
import { analyzeEmail } from "./voice-app";

export type SourceType = "outlook_email" | "gmail_email" | "whatsapp_text" | "twilio_call";

export type AnalysisStatus = {
  pipelineStatus: string;
  pipelineStep: string | null;
  classificationLabel: string | null;
  classificationConfidence: number | null;
  classificationReason: string | null;
  incidentFormId: number | null;
  errorMessage: string | null;
};

type StoredAnalysis = {
  classification_label: string | null;
  classification_confidence: number | null;
  classification_reason: string | null;
  incident_form_id: number | null;
  pipeline_status: string;
  pipeline_step: string | null;
  error_message: string | null;
};

export async function getExistingAnalysis(
  sourceType: SourceType,
  sourceId: string,
): Promise<StoredAnalysis | null> {
  try {
    const rows = await prisma.$queryRaw<StoredAnalysis[]>`
      SELECT classification_label, classification_confidence, classification_reason,
             incident_form_id, pipeline_status, pipeline_step, error_message
      FROM content_analysis
      WHERE source_type = ${sourceType} AND source_id = ${sourceId}
      LIMIT 1
    `;
    return rows[0] ?? null;
  } catch {
    return null;
  }
}

export async function getAnalysisMap(
  sourceType: SourceType,
  sourceIds: string[],
): Promise<Map<string, { label: string; incidentFormId: number | null }>> {
  if (sourceIds.length === 0) return new Map();
  try {
    const rows = await prisma.$queryRaw<
      { source_id: string; classification_label: string | null; incident_form_id: number | null }[]
    >`
      SELECT source_id, classification_label, incident_form_id
      FROM content_analysis
      WHERE source_type = ${sourceType}
        AND source_id = ANY(${sourceIds})
        AND pipeline_status = 'completed'
    `;
    const map = new Map<string, { label: string; incidentFormId: number | null }>();
    for (const r of rows) {
      map.set(r.source_id, {
        label: r.classification_label ?? "unknown",
        incidentFormId: r.incident_form_id,
      });
    }
    return map;
  } catch {
    return new Map();
  }
}

/**
 * Insert a pending record and return. The actual pipeline runs in the
 * caller's `after()` callback so the response goes back immediately.
 */
export async function markPending(opts: {
  sourceType: SourceType;
  sourceId: string;
  accountId: number;
  sender: string;
  contentPreview: string;
}): Promise<void> {
  try {
    await prisma.$executeRaw`
      INSERT INTO content_analysis (source_type, source_id, account_id, pipeline_status, content_preview, sender)
      VALUES (${opts.sourceType}, ${opts.sourceId}, ${opts.accountId}, 'pending', ${opts.contentPreview}, ${opts.sender})
      ON CONFLICT (source_type, source_id)
      DO UPDATE SET pipeline_status = 'pending', error_message = NULL
    `;
  } catch {
    // table may not exist yet
  }
}

/**
 * Run the voice-app pipeline and write the result to content_analysis.
 * Called from `after()` — runs after the response is sent to the client.
 */
export async function runPipeline(opts: {
  sourceType: SourceType;
  sourceId: string;
  subject: string;
  sender: string;
  body: string;
  receivedAt?: string;
}): Promise<void> {
  try {
    await prisma.$executeRaw`
      UPDATE content_analysis
      SET pipeline_step = 'classifying'
      WHERE source_type = ${opts.sourceType} AND source_id = ${opts.sourceId}
    `;

    const result = await analyzeEmail({
      subject: opts.subject,
      sender: opts.sender,
      body: opts.body,
      message_id: opts.sourceId,
      received_at: opts.receivedAt,
    });

    const classification = result.pipeline.classification;
    const incidentFormId = result.pipeline.database?.incident_form_id ?? null;

    await prisma.$executeRaw`
      UPDATE content_analysis
      SET pipeline_step = 'saving'
      WHERE source_type = ${opts.sourceType} AND source_id = ${opts.sourceId}
    `;

    await prisma.$executeRaw`
      UPDATE content_analysis
      SET classification_label = ${classification?.label ?? null},
          classification_confidence = ${classification?.confidence ?? null}::real,
          classification_reason = ${classification?.reason ?? null},
          incident_form_id = ${incidentFormId},
          pipeline_status = 'completed',
          pipeline_step = NULL
      WHERE source_type = ${opts.sourceType} AND source_id = ${opts.sourceId}
    `;
  } catch (err) {
    const errorMsg = err instanceof Error ? err.message : String(err);
    try {
      await prisma.$executeRaw`
        UPDATE content_analysis
        SET pipeline_status = 'failed', error_message = ${errorMsg}
        WHERE source_type = ${opts.sourceType} AND source_id = ${opts.sourceId}
      `;
    } catch {
      // DB write failed too
    }
  }
}

export async function getAnalysisStatus(
  sourceType: SourceType,
  sourceId: string,
): Promise<AnalysisStatus | null> {
  try {
    const rows = await prisma.$queryRaw<StoredAnalysis[]>`
      SELECT pipeline_status, pipeline_step, classification_label, classification_confidence,
             classification_reason, incident_form_id, error_message
      FROM content_analysis
      WHERE source_type = ${sourceType} AND source_id = ${sourceId}
      LIMIT 1
    `;
    const r = rows[0];
    if (!r) return null;
    return {
      pipelineStatus: r.pipeline_status,
      pipelineStep: r.pipeline_step,
      classificationLabel: r.classification_label,
      classificationConfidence: r.classification_confidence,
      classificationReason: r.classification_reason,
      incidentFormId: r.incident_form_id,
      errorMessage: r.error_message,
    };
  } catch {
    return null;
  }
}
