import { env } from "./env";

// Result shape returned by voice-app's /upload route.
// We only type the fields the dashboard cares about — the pipeline returns
// more, but using `unknown` for the rest keeps us honest about boundary trust.
export type PipelineResult = {
  filename: string;
  path?: string;
  file_size_mb?: number;
  pipeline: {
    transcription?: { status: string; text?: string; word_count?: number; quality_warning?: string; error?: string };
    incident_form?: { status: string; form_id?: string; confidence?: unknown; form?: Record<string, unknown>; error?: string };
    email?: { status: string; sent_to?: string; error?: string };
    database?: {
      status: string;
      file_id?: number;
      recording_session_id?: number;
      incident_form_id?: number;
      note?: string;
      error?: string;
    };
    transcripts?: { original?: string; dutch?: string };
  };
};

export type CallerMetadata = {
  callerName?: string;
  accountOrReference?: string;
  contactInfo?: string;
};

// Forward an audio file (Buffer or stream-friendly Blob) into the existing
// Python voice-app pipeline. The voice-app itself handles transcribe → AI form
// fill → email + DB writes. We just relay and surface the JSON result.
export async function analyzeAudio(
  audio: { filename: string; bytes: Buffer | Uint8Array; contentType: string },
  metadata: CallerMetadata = {}
): Promise<PipelineResult> {
  const form = new FormData();
  // Node's global FormData accepts Blob; Buffer→Uint8Array is a cheap conversion.
  const blob = new Blob([audio.bytes as BlobPart], { type: audio.contentType });
  form.append("file", blob, audio.filename);
  if (metadata.callerName) form.append("caller_name", metadata.callerName);
  if (metadata.accountOrReference) form.append("account_or_reference", metadata.accountOrReference);
  if (metadata.contactInfo) form.append("contact_info", metadata.contactInfo);

  const response = await fetch(env.voiceAppUploadUrl, { method: "POST", body: form });
  // voice-app may return 502 with a partial result body — we still want to surface it.
  const text = await response.text();
  let parsed: unknown = null;
  try { parsed = text ? JSON.parse(text) : null; } catch { /* fall through */ }

  if (!response.ok) {
    const err = (parsed && typeof parsed === "object" && "error" in parsed)
      ? (parsed as { error: string }).error
      : text.slice(0, 400);
    throw new Error(`voice-app /upload failed (${response.status}): ${err}`);
  }
  if (!parsed || typeof parsed !== "object") {
    throw new Error("voice-app /upload returned non-JSON body");
  }
  return parsed as PipelineResult;
}
