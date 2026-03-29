# Testing Guide

This guide validates the full local stack from startup through API, email, database, and telephony ingest smoke tests.

## Table of Contents

- [Scope](#scope)
- [Start The Stack](#start-the-stack)
- [Health Checks](#health-checks)
- [UI Test](#ui-test)
- [API Test](#api-test)
- [Formatter-Only Test](#formatter-only-test)
- [Telephony Ingest Smoke Test](#telephony-ingest-smoke-test)
- [Email Verification](#email-verification)
- [Database Verification](#database-verification)
- [Generate Test Audio](#generate-test-audio)
- [Common Problems](#common-problems)
- [Useful Commands](#useful-commands)
- [Service URLs](#service-urls)

## Scope

You will validate:
1. Service startup and health.
2. Real transcription pipeline.
3. AI form extraction behavior.
4. Email delivery to Mailpit.
5. Database storage.
6. Telephony webhook ingest path.

## Start The Stack

Linux/macOS:

```bash
docker compose --profile dev up -d --build
docker compose ps
```

Windows PowerShell:

```powershell
docker compose --profile dev up -d --build
docker compose ps
```

Expected:
- `support-voice-app` running.
- `support-transcriber` healthy (first run may take longer).
- `support-transcript-formatter` running.
- `support-email-sender` running.

## Health Checks

Linux/macOS:

```bash
curl -sS http://localhost:5000/health
curl -sS http://localhost:5001/health
curl -sS http://localhost:5002/health
curl -sS http://localhost:5010/health
```

Windows PowerShell:

```powershell
curl.exe -sS http://localhost:5000/health
curl.exe -sS http://localhost:5001/health
curl.exe -sS http://localhost:5002/health
curl.exe -sS http://localhost:5010/health
```

Each endpoint should return `{"status":"ok"}`.

## UI Test

1. Open `http://localhost:5000`.
2. Fill optional caller fields.
3. Upload audio or record in browser.
4. Submit and inspect JSON response.

Expected minimum markers:
- `pipeline.transcription.status = success`
- `pipeline.incident_form.status = completed`
- `pipeline.email.status = sent` (or SMTP success)
- `pipeline.database.status = stored`

## API Test

Linux/macOS:

```bash
curl -sS -X POST http://localhost:5000/upload \
   -F "file=@test_call.wav" \
   -F "caller_name=Alex Jansen" \
   -F "account_or_reference=AC-7781" \
   -F "contact_info=alex@example.com" | python3 -m json.tool
```

Windows PowerShell:

```powershell
curl.exe -sS -X POST http://localhost:5000/upload `
   -F "file=@test_call.wav" `
   -F "caller_name=Alex Jansen" `
   -F "account_or_reference=AC-7781" `
   -F "contact_info=alex@example.com"
```

## Formatter-Only Test

Linux/macOS:

```bash
curl -sS -X POST http://localhost:5001/format \
   -H "Content-Type: application/json" \
   -d '{
      "transcript": "Agent: Hello. Caller: My name is Alex Jansen. I cannot log into my account and this is urgent.",
      "metadata": {
         "caller_name": "Alex Jansen",
         "account_or_reference": "AC-7781",
         "contact_info": "alex@example.com"
      }
   }' | python3 -m json.tool
```

Windows PowerShell:

```powershell
$body = @'
{
   "transcript": "Agent: Hello. Caller: My name is Alex Jansen. I cannot log into my account and this is urgent.",
   "metadata": {
      "caller_name": "Alex Jansen",
      "account_or_reference": "AC-7781",
      "contact_info": "alex@example.com"
   }
}
'@
curl.exe -sS -X POST http://localhost:5001/format -H "Content-Type: application/json" -d $body
```

Expected:
- Caller identity fields are present.
- Issue category and priority are not empty.
- Summary is generated.

## Telephony Ingest Smoke Test

Linux/macOS:

```bash
chmod +x test_telephony_ingest.sh
./test_telephony_ingest.sh
```

Windows PowerShell:

```powershell
bash ./test_telephony_ingest.sh
```

Optional payload inspection:

Linux/macOS:

```bash
curl -sS http://localhost:5010/webhooks/example-payload | python3 -m json.tool
```

Windows PowerShell:

```powershell
curl.exe -sS http://localhost:5010/webhooks/example-payload
```

## Email Verification

1. Open `http://localhost:8025`.
2. Check latest message includes caller, issue, and summary data.

## Database Verification

Linux/macOS:

```bash
curl -sS http://localhost:5000/forms | python3 -m json.tool
```

Windows PowerShell:

```powershell
curl.exe -sS http://localhost:5000/forms
```

Optional single form lookup:

Linux/macOS:

```bash
curl -sS http://localhost:5000/forms/<form_id> | python3 -m json.tool
```

Windows PowerShell:

```powershell
curl.exe -sS http://localhost:5000/forms/<form_id>
```

## Generate Test Audio

Linux (record directly):

```bash
arecord -d 12 -f cd test_call.wav
```

Linux/macOS (if `espeak-ng` is installed):

```bash
espeak-ng -w test_call.wav "Hello support, my name is Alex Jansen, account AC 7781, I cannot log in and need urgent help."
```

Windows:
- Use any existing `.wav` or `.mp3` file.
- Or use browser recording directly from UI.

## Common Problems

1. `localhost:5000` not reachable:
    - Run `docker compose ps voice-app`.
    - Check `docker logs --tail 200 support-voice-app`.
    - Restart the stack.

2. Transcription failures:
    - Check `support-transcriber` health and logs.
    - Wait longer on first boot.

3. Generic AI output:
    - Verify Ollama endpoint (`http://localhost:11434/api/tags`).
    - Check formatter logs.

4. Missing emails:
    - Verify `SMTP_HOST=mailpit`, `SMTP_PORT=1025`.
    - Check `support-email-sender` logs.

## Useful Commands

Linux/macOS:

```bash
docker compose logs -f support-voice-app
docker compose logs -f support-transcriber
docker compose logs -f support-transcript-formatter
docker compose logs -f support-email-sender
docker compose restart support-voice-app
docker compose --profile dev down
docker compose --profile dev down -v
```

Windows PowerShell:

```powershell
docker compose logs -f support-voice-app
docker compose logs -f support-transcriber
docker compose logs -f support-transcript-formatter
docker compose logs -f support-email-sender
docker compose restart support-voice-app
docker compose --profile dev down
docker compose --profile dev down -v
```

## Service URLs

| Service | URL |
|---|---|
| Voice App UI/API | http://localhost:5000 |
| Formatter API | http://localhost:5001 |
| Email Sender API | http://localhost:5002 |
| Telephony Ingest | http://localhost:5010 |
| Transcriber Docs | http://localhost:9000/docs |
| n8n | http://localhost:5678 |
| Mailpit | http://localhost:8025 |
