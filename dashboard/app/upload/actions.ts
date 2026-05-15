"use server";

import { revalidatePath } from "next/cache";
import { prisma } from "@/lib/prisma";
import { analyzeAudio, type PipelineResult } from "@/lib/voice-app";

export type UploadResult =
  | { ok: true; result: PipelineResult; incidentId: number | null }
  | { ok: false; error: string };

const MAX_BYTES = 50 * 1024 * 1024; // matches voice-app MAX_FILE_SIZE_MB default
const ALLOWED_PREFIX = "audio/";
const ALLOWED_EXT = /\.(wav|mp3|ogg|flac|m4a|webm)$/i;

export async function uploadAndAnalyzeAudio(formData: FormData): Promise<UploadResult> {
  const file = formData.get("audio");
  if (!(file instanceof File) || file.size === 0) {
    return { ok: false, error: "Please choose an audio file." };
  }
  if (file.size > MAX_BYTES) {
    return { ok: false, error: `File is too large (max ${MAX_BYTES / 1024 / 1024}MB).` };
  }
  // voice-app validates types itself, but we surface a friendlier message early.
  const looksAudio = (file.type && file.type.startsWith(ALLOWED_PREFIX)) || ALLOWED_EXT.test(file.name);
  if (!looksAudio) {
    return { ok: false, error: "Unsupported file type. Use wav/mp3/ogg/flac/m4a/webm." };
  }

  const callerName = (formData.get("callerName") as string | null)?.trim() || undefined;
  const accountOrReference = (formData.get("accountOrReference") as string | null)?.trim() || undefined;
  const contactInfo = (formData.get("contactInfo") as string | null)?.trim() || undefined;

  try {
    const bytes = Buffer.from(await file.arrayBuffer());
    const result = await analyzeAudio(
      { filename: file.name, bytes, contentType: file.type || "application/octet-stream" },
      { callerName, accountOrReference, contactInfo }
    );

    // The pipeline persists into the same support_db Postgres we're connected to.
    // Resolve the incident form id so we can link straight to the detail view.
    const formId = result.pipeline.incident_form?.form_id ?? null;
    let incidentId: number | null = result.pipeline.database?.incident_form_id ?? null;
    if (incidentId == null && formId) {
      const row = await prisma.incidentGeneralInformation.findFirst({
        where: { formData: { path: ["form_id"], equals: formId } },
        select: { incidentFormId: true },
      });
      incidentId = row?.incidentFormId ?? null;
    }

    revalidatePath("/incidents");
    revalidatePath("/");
    return { ok: true, result, incidentId };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return { ok: false, error: message };
  }
}
