# Telephony Integration Setup

This document captures the practical path from local PBX testing to provider pilot, including the trial-and-error lessons from our lab setup.

## Table of Contents

- [Current Status](#current-status)
- [Implemented Components](#implemented-components)
- [End-To-End Flow](#end-to-end-flow)
- [Webhook Contract](#webhook-contract)
- [Local Lab Setup](#local-lab-setup)
- [Known Pitfalls And Fixes](#known-pitfalls-and-fixes)
- [Manual External Actions](#manual-external-actions)
- [Team Backlog](#team-backlog)
- [Definition Of Ready For Pilot](#definition-of-ready-for-pilot)

## Current Status

What is working now:
1. Internal extension calling works in the FreePBX lab.
2. Two-way audio was validated in local device-to-device call testing.
3. `telephony-ingest` receives webhook payloads and forwards audio to `voice-app`.
4. Existing pipeline still handles transcript, formatting, email, and DB storage.

What is not production-ready yet:
1. Provider-side webhook delivery and retry are not configured.
2. Idempotency and signature verification are not implemented.
3. Telephony metadata is not yet persisted in dedicated DB tables.

## Implemented Components

1. Service `telephony-ingest`.
2. Endpoint `POST /webhooks/recording-complete`.
3. Raw event persistence under `/data/shared/telephony-events`.
4. Forwarding from telephony event to `voice-app /upload`.
5. Local helper script `test_telephony_ingest.sh`.

## End-To-End Flow

1. PBX or provider emits `recording-complete` webhook.
2. `telephony-ingest` resolves recording from `recording_path` or `recording_url`.
3. Recording is forwarded to `voice-app /upload`.
4. Existing pipeline runs:
   - transcribe,
   - format incident report,
   - send email,
   - persist form.

## Webhook Contract

Minimal payload:

```json
{
  "event_id": "evt-123",
  "call_id": "call-abc",
  "answered": true,
  "recording_path": "/data/shared/uploads/test_call.wav"
}
```

Recommended extended payload:

```json
{
  "provider": "pbx",
  "source_number": "+31-10-0000000",
  "destination_number": "+31-10-1111111",
  "caller_id": "+31-6-12345678",
  "started_at": "2026-03-26T09:00:00Z",
  "ended_at": "2026-03-26T09:03:20Z",
  "recording_url": "https://example.invalid/recordings/call-abc.wav"
}
```

Authentication:
- Set `TELEPHONY_WEBHOOK_TOKEN`.
- Send `X-Telephony-Token` header.

## Local Lab Setup

1. Start app stack:

Linux/macOS:

```bash
docker compose --profile dev up -d --build
```

Windows PowerShell:

```powershell
docker compose --profile dev up -d --build
```

2. Start telephony lab stack:

Linux/macOS:

```bash
docker compose -f docker-compose.telephony-lab.yml up -d
```

Windows PowerShell:

```powershell
docker compose -f docker-compose.telephony-lab.yml up -d
```

3. Configure FreePBX:
   - Create extensions (for example 1001, 1002).
   - Set ring group (for example 600).
   - Route unanswered calls to voicemail.
   - Enable recording for answered and unanswered scenarios.

4. Configure softphones:
   - SIP server: machine running FreePBX.
   - Username: extension number.
   - Password: extension secret from FreePBX extension settings.

5. Validate ingest path:

Linux/macOS:

```bash
./test_telephony_ingest.sh
```

Windows PowerShell:

```powershell
bash ./test_telephony_ingest.sh
```

## Known Pitfalls And Fixes

1. Auth keeps failing even with correct extension number:
   - Cause: User Manager password was confused with extension secret.
   - Fix: Use extension secret from FreePBX extension config.

2. One-way audio or call drops after about 30 seconds:
   - Cause: RTP/NAT transport mismatch.
   - Fix:
     - Keep endpoint media options consistent (`direct_media=no`, `rtp_symmetric=yes`, `rewrite_contact=yes`, `force_rport=yes`).
     - Ensure transport `local_net` reflects local LAN.
     - Avoid incorrect external media/signaling advertisement in LAN-only lab.

3. Voicemail path missing (`No application 'VoiceMail'`):
   - Cause: module conflict in this lab image.
   - Fix: disable conflicting external MWI modules and reload/restart Asterisk.

4. FreePBX reload intermittently failing (`/tmp/cron.error` permission error):
   - Impact: GUI applies may be inconsistent.
   - Workaround: verify effective Asterisk config via CLI and prefer explicit service/container restarts when needed.

5. Teammate setup assumptions:
   - Each teammate must set SIP server to their own lab host IP/hostname.
   - If they run PBX locally, they should use their own local network values.

## Manual External Actions

These are outside this repository:

1. Choose provider/PBX hosting region and privacy model.
2. Port personal and work numbers.
3. Publish `telephony-ingest` over HTTPS.
4. Configure provider webhook URL and retry policy.
5. Set production secrets:
   - `TELEPHONY_WEBHOOK_TOKEN`
   - optional recording URL auth headers.
6. Finalize legal/consent policy for call recording.

## Team Backlog

Telephony/PBX:
1. Final DID routing for both numbers.
2. Guaranteed recordings for answered and unanswered calls.
3. Reliable webhook delivery/retry.

Backend:
1. Signature verification in `telephony-ingest`.
2. Idempotency for duplicate events.
3. Retry queue for forwarding failures.
4. DB storage for telephony metadata.

AI/Pipeline:
1. Tune extraction for phone-quality audio.
2. Improve short voicemail handling.

Security/Privacy:
1. Retention and deletion policy.
2. Access control and audit requirements.

## Definition Of Ready For Pilot

1. Both numbers are routed through provider into one call flow.
2. Both answered and unanswered calls produce recordings.
3. Webhook reaches `telephony-ingest` reliably.
4. End-to-end form and email succeed for both call types.
5. Failures are observable and retryable.
