import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { env } from "@/lib/env";

export async function POST(req: NextRequest) {
  const formData = await req.formData();
  const form: Record<string, string> = {};
  formData.forEach((v, k) => {
    form[k] = String(v);
  });

  const callSid = form["CallSid"] ?? "";
  const recordingSid = form["RecordingSid"] ?? "";
  const recordingUrl = form["RecordingUrl"] ?? "";
  const recordingDuration = form["RecordingDuration"];
  const fromNumber = form["From"] ?? "";
  const toNumber = form["To"] ?? "";

  const duration =
    recordingDuration && /^\d+$/.test(recordingDuration)
      ? parseInt(recordingDuration, 10)
      : null;

  console.log(
    `[recording-status] CallSid=${callSid} RecordingSid=${recordingSid} duration=${duration} from=${fromNumber}`,
  );

  if (!recordingUrl) {
    console.error("[recording-status] No RecordingUrl in payload — skipping");
    return new NextResponse(null, { status: 204 });
  }

  // 1. Persist call metadata to DB
  let callId: number | null = null;
  try {
    const conversation = await prisma.callConversation.upsert({
      where: { contactPhone: fromNumber },
      update: { lastCallAt: new Date() },
      create: { contactPhone: fromNumber, lastCallAt: new Date() },
    });

    const call = await prisma.twilioCall.upsert({
      where: { callSid },
      update: {
        status: "processing",
        durationSeconds: duration ?? undefined,
        recordingSid: recordingSid || undefined,
        recordingTwilioUrl: recordingUrl || undefined,
      },
      create: {
        conversationId: conversation.id,
        callSid,
        direction: "inbound",
        fromNumber,
        toNumber,
        status: "processing",
        durationSeconds: duration,
        recordingSid: recordingSid || null,
        recordingTwilioUrl: recordingUrl || null,
      },
    });
    callId = call.id;
  } catch (err) {
    console.error("[recording-status] DB insert failed:", err);
  }

  // 2. Fetch MP3 from Twilio into memory (no local disk storage)
  let mp3Buffer: Buffer | null = null;
  try {
    const mp3Url = recordingUrl.endsWith(".mp3")
      ? recordingUrl
      : `${recordingUrl}.mp3`;
    const sid = process.env.TWILIO_ACCOUNT_SID ?? "";
    const token = process.env.TWILIO_AUTH_TOKEN ?? "";
    const auth = "Basic " + Buffer.from(`${sid}:${token}`).toString("base64");

    const initial = await fetch(mp3Url, {
      headers: { Authorization: auth },
      redirect: "manual",
    });
    let res: Response;
    const location = initial.headers.get("location");
    if (initial.status >= 300 && initial.status < 400 && location) {
      res = await fetch(location);
    } else {
      res = initial;
    }

    if (res.ok) {
      mp3Buffer = Buffer.from(await res.arrayBuffer());
      console.log(
        `[recording-status] Fetched ${mp3Buffer.length} bytes from Twilio`,
      );
    } else {
      console.error(
        `[recording-status] MP3 download failed: ${res.status} ${res.statusText}`,
      );
    }
  } catch (err) {
    console.error("[recording-status] MP3 download error:", err);
    if (callId) {
      await prisma.twilioCall
        .update({
          where: { id: callId },
          data: {
            status: "failed",
            errorMessage: `Recording download failed: ${err}`,
          },
        })
        .catch(() => {});
    }
  }

  // 3. Forward to voice-app pipeline for transcription + AI
  if (mp3Buffer) {
    try {
      const voiceAppUrl = env.voiceAppUploadUrl;
      const filename = `${safeStem(callSid)}_${safeStem(recordingSid)}.mp3`;
      const fd = new FormData();
      fd.append(
        "file",
        new Blob([new Uint8Array(mp3Buffer)], { type: "audio/mpeg" }),
        filename,
      );
      fd.append("contact_info", fromNumber);
      fd.append("account_or_reference", callSid);
      fd.append("telephony_source_number", toNumber);
      fd.append("telephony_call_mode", "answered_call");
      fd.append("telephony_provider", "twilio_voice");

      console.log(
        `[recording-status] Forwarding to voice-app: ${voiceAppUrl}`,
      );
      const pipelineRes = await fetch(voiceAppUrl, {
        method: "POST",
        body: fd,
        signal: AbortSignal.timeout(900_000),
      });

      if (pipelineRes.ok) {
        const result = await pipelineRes.json();
        const pipeline = result?.pipeline ?? {};
        const incidentFormId = pipeline?.database?.incident_form_id ?? null;
        const transcriptText = pipeline?.transcription?.text ?? null;
        console.log(
          `[recording-status] Pipeline done — incident_form_id=${incidentFormId}`,
        );

        if (callId) {
          await prisma.twilioCall.update({
            where: { id: callId },
            data: {
              status: "completed",
              incidentFormId: incidentFormId
                ? parseInt(String(incidentFormId), 10)
                : undefined,
              transcriptText: transcriptText ?? undefined,
            },
          });
        }
      } else {
        const text = await pipelineRes.text().catch(() => "");
        console.error(
          `[recording-status] Voice-app returned ${pipelineRes.status}: ${text}`,
        );
        if (callId) {
          await prisma.twilioCall
            .update({
              where: { id: callId },
              data: {
                status: "recorded",
                errorMessage: `Pipeline returned ${pipelineRes.status}`,
              },
            })
            .catch(() => {});
        }
      }
    } catch (err) {
      console.error("[recording-status] Voice-app forward failed:", err);
      if (callId) {
        await prisma.twilioCall
          .update({
            where: { id: callId },
            data: {
              status: "recorded",
              errorMessage: `Pipeline failed: ${err}`,
            },
          })
          .catch(() => {});
      }
    }
  }

  return new NextResponse(null, { status: 204 });
}

function safeStem(v: string): string {
  return v.replace(/[^a-zA-Z0-9_-]/g, "_").slice(0, 120) || "call";
}
