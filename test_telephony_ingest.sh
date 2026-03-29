#!/usr/bin/env bash
set -euo pipefail

TELEPHONY_URL="${TELEPHONY_URL:-http://localhost:5010/webhooks/recording-complete}"
TOKEN="${TELEPHONY_WEBHOOK_TOKEN:-}"
RECORDING_PATH="${1:-/data/shared/uploads/test_call.wav}"

payload=$(cat <<JSON
{
  "provider": "pbx",
  "event_id": "evt-local-$(date +%s)",
  "call_id": "call-local-$(date +%s)",
  "source_number": "+31-10-0000000",
  "destination_number": "+31-10-1111111",
  "caller_id": "+31-6-12345678",
  "answered": true,
  "recording_path": "${RECORDING_PATH}",
  "started_at": "2026-03-26T09:00:00Z",
  "ended_at": "2026-03-26T09:03:20Z"
}
JSON
)

if [ -n "$TOKEN" ]; then
  curl -sS -X POST "$TELEPHONY_URL" \
    -H 'Content-Type: application/json' \
    -H "X-Telephony-Token: $TOKEN" \
    -d "$payload" | python3 -m json.tool
else
  curl -sS -X POST "$TELEPHONY_URL" \
    -H 'Content-Type: application/json' \
    -d "$payload" | python3 -m json.tool
fi
