# Telephony Integration Foundation

This document defines the minimum implementation path for taking the current audio-processing prototype into real phone-call intake.

## What Is Already Implemented In This Branch

1. New service: `telephony-ingest`.
2. New endpoint: `POST /webhooks/recording-complete`.
3. Event persistence: raw webhook payloads are saved under `/data/shared/telephony-events`.
4. Forwarding: webhook recording audio is forwarded into existing `voice-app /upload` pipeline.
5. Local smoke-test script: `test_telephony_ingest.sh`.

## Flow Supported Right Now

1. Telephony provider or PBX sends `recording-complete` webhook.
2. Service resolves recording from either:
   - `recording_path` (local/shared file path), or
   - `recording_url` (downloaded over HTTP/HTTPS).
3. Service forwards audio to `voice-app /upload`.
4. Existing pipeline runs unchanged:
   - transcribe,
   - format incident form,
   - send email,
   - store data.

## Webhook Contract (Current)

Required shape (minimal):

```json
{
  "event_id": "evt-123",
  "call_id": "call-abc",
  "answered": true,
  "recording_path": "/data/shared/uploads/test_call.wav"
}
```

Optional but recommended:

```json
{
  "provider": "pbx",
  "source_number": "+31-10-0000000",
  "destination_number": "+31-10-1111111",
  "caller_id": "+31-6-12345678",
  "started_at": "2026-03-26T09:00:00Z",
  "ended_at": "2026-03-26T09:03:20Z",
  "recording_url": "https://..."
}
```

Authentication:
- Configure `TELEPHONY_WEBHOOK_TOKEN` and send header `X-Telephony-Token`.

## Team Backlog (Who Works On What)

### A. Telephony/PBX Team

1. Port both numbers (personal + work) into one provider account.
2. Configure inbound routes by DID:
   - source tag `personal`,
   - source tag `work`.
3. Enable recording for:
   - answered calls,
   - unanswered voicemail calls.
4. Configure recording-complete webhook delivery.
5. Ensure retry policy on webhook delivery.

### B. Backend Team

1. Add signature verification (provider-specific) in `telephony-ingest`.
2. Add idempotency for duplicate webhook events.
3. Add durable queue/retry for forwarding failures.
4. Store telephony metadata in DB tables.
5. Add structured status endpoints for operations.

### C. AI/Pipeline Team

1. Tune transcript quality for phone-bandwidth audio.
2. Add phone-call-specific extraction heuristics.
3. Improve low-confidence field handling for short voicemails.

### D. Security/Privacy Team

1. Confirm EU-only hosting and backups.
2. Define retention/deletion for recordings and transcripts.
3. Lock down access controls and audit logs.
4. Add consent announcement requirements for call recording.

## Manual Actions Required From You

These are external and cannot be performed from this repository:

1. Choose and provision your EU telephony/PBX provider.
2. Initiate number porting for both phone numbers.
3. Expose `telephony-ingest` publicly over HTTPS (reverse proxy + TLS).
4. Configure provider webhook endpoint URL.
5. Set production secrets:
   - `TELEPHONY_WEBHOOK_TOKEN`
   - optional recording URL auth values.
6. Approve recording consent wording and legal policy.

## Local Test Commands

```bash
# Start stack (with dev profile for Mailpit)
docker compose --profile dev up -d --build

# Verify telephony ingest service
curl -sS http://localhost:5010/health

# Trigger local telephony webhook simulation
./test_telephony_ingest.sh /data/shared/uploads/test_en_short.wav
```

## Definition Of Ready For Provider Pilot

1. Both numbers route into one telephony account.
2. Both answered and unanswered calls produce recordings.
3. Recording-complete webhook reaches `telephony-ingest`.
4. End-to-end form + email succeeds for each call type.
5. Failure and retry paths are observable.
