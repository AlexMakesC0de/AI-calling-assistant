#!/usr/bin/env bash
###############################################################################
# test_pipeline.sh – End-to-end test of the support call pipeline.
#
# Usage:
#   ./test_pipeline.sh <audio_file.wav>
#
# Example:
#   ./test_pipeline.sh call_recording.wav
#
# What it does:
#   Uploads the audio file to the voice-app, which automatically:
#     1. Transcribes it with speaker diarization (identifies who said what)
#     2. Sends the diarized transcript to the AI formatter (fills out incident form)
#     3. Emails the completed form to the support team
#
#   After running, check Mailpit at http://localhost:8025 to see the email.
###############################################################################
set -euo pipefail

VOICE_APP_URL="${VOICE_APP_URL:-http://localhost:5000}"
AUDIO_FILE="${1:?Usage: $0 <audio_file.wav>}"

if [ ! -f "$AUDIO_FILE" ]; then
    echo "❌ File not found: $AUDIO_FILE"
    exit 1
fi

echo "============================================"
echo "  Support Call Pipeline – End-to-End Test"
echo "============================================"
echo ""
echo "📤 Uploading '$AUDIO_FILE'..."
echo "   The pipeline will run automatically:"
echo "     1. Transcribe + diarize speakers"
echo "     2. Fill incident form (AI)"
echo "     3. Email support team"
echo ""

RESPONSE=$(curl -s -X POST "${VOICE_APP_URL}/upload" \
    -F "file=@${AUDIO_FILE}")

echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
echo ""

# Check pipeline status
PIPELINE_STATUS=$(echo "$RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    p = data.get('pipeline', {})
    tx = p.get('transcription', {}).get('status', 'unknown')
    form = p.get('incident_form', {}).get('status', 'unknown')
    email = p.get('email', {}).get('status', 'unknown')
    print(f'transcription={tx}')
    print(f'form={form}')
    print(f'email={email}')
    if tx == 'success' and form == 'completed' and email == 'sent':
        sys.exit(0)
    else:
        sys.exit(1)
except Exception as e:
    print(f'error={e}', file=sys.stderr)
    sys.exit(1)
" 2>&1)

if [ $? -eq 0 ]; then
    echo "============================================"
    echo "  ✅ Pipeline complete!"
    echo ""
    echo "  Check your email at: http://localhost:8025"
    echo "============================================"
else
    echo "============================================"
    echo "  ❌ Pipeline had issues:"
    echo "$PIPELINE_STATUS"
    echo ""
    echo "  Check logs: docker compose logs support-voice-app"
    echo "============================================"
    exit 1
fi
