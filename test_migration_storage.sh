#!/usr/bin/env bash
set -euo pipefail

VOICE_APP_URL="${VOICE_APP_URL:-http://localhost:5000}"
DB_CONTAINER="${DB_CONTAINER:-support-db}"
DB_USER="${DB_USER:-support}"
DB_NAME="${DB_NAME:-support_db}"
AUDIO_FILE="${1:-test_en_short.wav}"

if [ ! -f "$AUDIO_FILE" ]; then
  echo "Missing audio file: $AUDIO_FILE"
  exit 1
fi

read_counts() {
  docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -t -A -c "
    SELECT
      (SELECT COUNT(*) FROM incident_forms),
      (SELECT COUNT(*) FROM recordsession),
      (SELECT COUNT(*) FROM file),
      (SELECT COUNT(*) FROM transcriptchunk);
  "
}

parse_csv_counts() {
  IFS='|' read -r forms sessions files chunks <<< "$1"
  echo "$forms" "$sessions" "$files" "$chunks"
}

baseline_raw="$(read_counts)"
read -r base_forms base_sessions base_files base_chunks <<< "$(parse_csv_counts "$baseline_raw")"

echo "Baseline counts: incident_forms=$base_forms recordsession=$base_sessions file=$base_files transcriptchunk=$base_chunks"

echo "Uploading: $AUDIO_FILE"
response="$(curl -s -X POST "${VOICE_APP_URL}/upload" -F "file=@${AUDIO_FILE}")"
echo "$response" | python3 -m json.tool >/dev/null 2>&1 || {
  echo "Upload response is not valid JSON"
  echo "$response"
  exit 1
}

echo "$response" | python3 -c '
import json, sys
obj = json.load(sys.stdin)
p = obj.get("pipeline", {})
tx = p.get("transcription", {}).get("status")
form = p.get("incident_form", {}).get("status")
email = p.get("email", {}).get("status")
db = p.get("database", {}).get("status")
legacy = p.get("database", {}).get("incident_forms")
projection = p.get("database", {}).get("storage_projection")
print(f"transcription={tx}")
print(f"incident_form={form}")
print(f"email={email}")
print(f"database={db}")
print(f"database.incident_forms={legacy}")
print(f"database.storage_projection={projection}")
ok = (
    tx == "success"
    and form == "completed"
    and email == "sent"
    and db == "stored"
    and legacy == "stored"
    and projection == "stored"
)
sys.exit(0 if ok else 1)
' || {
  echo "Pipeline status check failed"
  exit 1
}

after_raw="$(read_counts)"
read -r after_forms after_sessions after_files after_chunks <<< "$(parse_csv_counts "$after_raw")"

echo "After counts: incident_forms=$after_forms recordsession=$after_sessions file=$after_files transcriptchunk=$after_chunks"

if [ "$after_forms" -le "$base_forms" ]; then
  echo "Expected incident_forms to increase"
  exit 1
fi
if [ "$after_sessions" -le "$base_sessions" ]; then
  echo "Expected recordsession to increase"
  exit 1
fi
if [ "$after_files" -le "$base_files" ]; then
  echo "Expected file to increase"
  exit 1
fi
if [ "$after_chunks" -le "$base_chunks" ]; then
  echo "Expected transcriptchunk to increase"
  exit 1
fi

echo "Migration validation passed"
