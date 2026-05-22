# whatsapp-ingest

Prototype WhatsApp adapter sitting alongside `telephony-ingest`. Receives
Twilio WhatsApp webhooks (text, media, voice notes), forwards audio into the
existing `voice-app` `/upload` pipeline so transcription + form-fill + email
all keep working unchanged, and exposes `/send` for outbound replies.

The goal is **feasibility validation** for the client's "WhatsApp calls /
messages / media" ask — not production. See *What this proves vs. doesn't*
below.

## Endpoints

| Method | Path                    | Purpose                                              |
| ------ | ----------------------- | ---------------------------------------------------- |
| GET    | `/health`               | Liveness; reports whether Twilio creds are present.  |
| POST   | `/webhooks/inbound`     | Twilio "When a message comes in" webhook.            |
| POST   | `/webhooks/status`      | Optional Twilio status callback.                     |
| POST   | `/send`                 | Outbound text + media. JSON `{to, body?, media_url?}`. |

Inbound voice notes (audio/ogg from WhatsApp) are downloaded with Twilio
Basic Auth and POSTed to `voice-app:5000/upload` with `telephony_call_mode=whatsapp_voice_note`,
so they show up in incident forms tagged as WhatsApp.

## 1. Get a Twilio sandbox

1. Sign up at [twilio.com](https://www.twilio.com) (free trial works).
2. In Console → **Messaging → Try it out → Send a WhatsApp message**, you'll
   see a sandbox number (typically `+1 415 523 8886`) and a join code like
   `join example-word`.
3. Save these values into `.env` at the repo root:

   ```
   TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   TWILIO_AUTH_TOKEN=your-auth-token
   TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
   ```

4. From your phone, send `join example-word` to that number on WhatsApp.
   You'll get an acknowledgement. Repeat for any other test devices.

## 2. Expose the service publicly

Twilio needs to reach `whatsapp-ingest` over the public internet.

```powershell
docker compose up -d whatsapp-ingest
# in a separate terminal:
ngrok http 5011
```

Copy the `https://xxxx.ngrok.app` URL ngrok prints, then set:

```
WHATSAPP_PUBLIC_BASE_URL=https://xxxx.ngrok.app
```

and restart the service so signature validation matches the public URL:

```powershell
docker compose up -d whatsapp-ingest
```

## 3. Point Twilio at the webhook

In Console → **Messaging → Try it out → Sandbox settings**:

- **When a message comes in** → `https://xxxx.ngrok.app/webhooks/inbound` (HTTP POST)
- **Status callback URL** → `https://xxxx.ngrok.app/webhooks/status` (optional)

## 4. Test inbound

From the joined phone, message the sandbox number:

- **Text:** "hello" → you should receive the auto-ack reply.
- **Voice note:** hold the mic icon and record → the file is forwarded to
  voice-app; check the dashboard incidents view + email-sender / Mailpit
  for the resulting form. Audio archive lands in
  `local-storage/shared/whatsapp-media/`.
- **Image / PDF:** archived to `whatsapp-media/`, no pipeline action yet.

Raw webhook payloads are saved to `local-storage/shared/whatsapp-events/`
for debugging.

## 5. Test outbound

```bash
curl -X POST http://localhost:5011/send \
  -H "Content-Type: application/json" \
  -d '{"to":"+15551234567","body":"Hello from the prototype"}'
```

For media, pass any public HTTPS URL (a Twilio-hosted media URL works once
you've received a message):

```bash
curl -X POST http://localhost:5011/send \
  -H "Content-Type: application/json" \
  -d '{"to":"+15551234567","body":"Receipt attached","media_url":"https://example.com/receipt.pdf"}'
```

## What this proves vs. doesn't

**Validated by this prototype**

- Inbound WhatsApp text + media + voice notes flow end-to-end into your
  existing transcription pipeline.
- Outbound text + media sending works against any opted-in number.
- Twilio signature validation, status callbacks, persistence of payloads
  and media for audit.

**Not validated — still open questions for the client**

- **Voice calls.** WhatsApp business-to-user voice calling is Meta's
  *WhatsApp Business Calling API* (GA 2025), **not** Twilio Programmable
  Voice. Requires verified Meta Business account, per-session user
  opt-in, and is not available in every region. Twilio does not fully
  proxy it yet. Plan a separate spike against the Meta Cloud API.
- **Production sender.** The sandbox FROM number cannot message arbitrary
  users — only ones who joined it. Going live requires a Meta Business
  verification + an approved WhatsApp Business Sender on Twilio.
- **Templates / outside the 24-hour session window.** Business-initiated
  messages outside the customer's 24-hour reply window require
  pre-approved message templates. The `/send` endpoint accepts a `body`
  string today; template support is a follow-up.
- **Storage / GDPR.** Inbound media is archived to a shared volume. For
  production, wire it into the same retention + redaction policy the
  voice recordings use.
