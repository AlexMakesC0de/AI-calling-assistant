import { env } from "./env";

export type TranscriberResult = {
  text: string;
  plain_text: string;
  word_count: number;
  speakers_detected: number;
  diarized: boolean;
  detected_language: string;
  language_probability: number;
  segments: Array<{ speaker: number; text: string; start: number; end: number }>;
  processing_time_seconds: number;
};

export async function transcribeAudio(audio: {
  filename: string;
  bytes: Buffer | Uint8Array;
  contentType: string;
}): Promise<TranscriberResult> {
  const form = new FormData();
  const blob = new Blob([audio.bytes as BlobPart], { type: audio.contentType });
  form.append("file", blob, audio.filename);

  const response = await fetch(`${env.transcriberBaseUrl}/transcribe`, {
    method: "POST",
    body: form,
    signal: AbortSignal.timeout(300_000),
  });

  const text = await response.text();
  let parsed: unknown = null;
  try {
    parsed = text ? JSON.parse(text) : null;
  } catch {}

  if (!response.ok) {
    const err =
      parsed && typeof parsed === "object" && "error" in parsed
        ? (parsed as { error: string }).error
        : text.slice(0, 400);
    throw new Error(`Transcriber failed (${response.status}): ${err}`);
  }

  if (!parsed || typeof parsed !== "object") {
    throw new Error("Transcriber returned non-JSON body");
  }

  return parsed as TranscriberResult;
}
