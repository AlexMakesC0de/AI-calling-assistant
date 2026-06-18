import { NextRequest, NextResponse } from "next/server";

const GREETING_TEXT =
  process.env.CALL_GREETING_TEXT ??
  "Thank you for calling support. Please describe your issue after the tone.";
const MAX_RECORDING_SECONDS = parseInt(
  process.env.CALL_MAX_RECORDING_SECONDS ?? "300",
  10,
);
const PUBLIC_BASE =
  process.env.PUBLIC_WEBHOOK_BASE_URL ?? "https://ai-calling-assistant-production.up.railway.app";

export async function POST(req: NextRequest) {
  const form = await req.formData();
  const callSid = form.get("CallSid") ?? "unknown";
  const from = form.get("From") ?? "";
  const to = form.get("To") ?? "";
  console.log(`[voice] Inbound call from=${from} to=${to} CallSid=${callSid}`);

  const recordingCallback = `${PUBLIC_BASE.replace(/\/$/, "")}/webhook/recording-status`;

  const twiml = `<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice">${escapeXml(GREETING_TEXT)}</Say>
  <Record
    maxLength="${MAX_RECORDING_SECONDS}"
    recordingStatusCallback="${escapeXml(recordingCallback)}"
    recordingStatusCallbackMethod="POST"
    recordingStatusCallbackEvent="completed"
    playBeep="true"
  />
  <Say>We did not receive a recording. Goodbye.</Say>
  <Hangup/>
</Response>`;

  return new NextResponse(twiml, {
    status: 200,
    headers: { "Content-Type": "application/xml" },
  });
}

function escapeXml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
