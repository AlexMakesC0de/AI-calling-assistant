# Testing Guide

This guide is OS-agnostic and covers both UI and API testing paths.

## Scope

You will validate:
1. Service health
2. Real transcription
3. AI form extraction
4. Email delivery to Mailpit
5. Caller field overrides (Name/Account/Contact)

## 1. Start The Stack

Linux/macOS:

```bash
docker compose --profile dev up -d --build
```

Windows PowerShell:

```powershell
docker compose --profile dev up -d --build
```

Check status:

```bash
docker compose ps
```

Expected:
- `support-voice-app` healthy
- `support-transcriber` healthy (can take longer on first run)
- `support-transcript-formatter` healthy
- `support-email-sender` healthy

## 2. Health Checks

```bash
curl -sS http://localhost:5000/health
curl -sS http://localhost:5001/health
curl -sS http://localhost:5002/health
```

Each should return `{"status":"ok"}`.

## 3. UI Test (Recommended Demo Flow)

1. Open `http://localhost:5000`
2. Fill optional caller override fields:
   - Caller name
   - Account/reference
   - Contact info
3. Choose one path:
   - Upload existing audio
   - Record audio in browser, then send
4. Inspect response panel

Expected minimum success markers:
- `pipeline.transcription.status = success`
- `pipeline.incident_form.status = completed`
- `pipeline.email.status = sent` (or configured SMTP success)
- `pipeline.database.status = stored`

Expected caller override behavior:
- `pipeline.incident_form.form.caller_information.name` uses provided caller name
- `...account_or_reference` uses provided account/reference
- `...contact_info` uses provided contact

## 4. API Test (CLI)

### Linux/macOS

```bash
curl -sS -X POST http://localhost:5000/upload \
  -F "file=@test_call.wav" \
  -F "caller_name=Alex Jansen" \
  -F "account_or_reference=AC-7781" \
  -F "contact_info=alex@example.com" | python3 -m json.tool
```

### Windows PowerShell

```powershell
curl.exe -sS -X POST http://localhost:5000/upload `
  -F "file=@test_call.wav" `
  -F "caller_name=Alex Jansen" `
  -F "account_or_reference=AC-7781" `
  -F "contact_info=alex@example.com"
```

## 5. Formatter-Only Test

Use this to isolate local AI extraction from ASR.

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

Expected:
- `caller_information.name = Alex Jansen`
- `issue.category` and `issue.priority` populated
- `call_summary` populated

## 6. Email Verification

Open Mailpit:

`http://localhost:8025`

Check latest message body includes:
- Caller information
- Issue + resolution
- Call summary

## 7. Database Verification

```bash
curl -sS http://localhost:5000/forms | python3 -m json.tool
```

Optional single form lookup:

```bash
curl -sS http://localhost:5000/forms/<form_id> | python3 -m json.tool
```

## 8. Generate Test Audio

Linux (record):

```bash
arecord -d 12 -f cd test_call.wav
```

Linux/macOS (espeak-ng if installed):

```bash
espeak-ng -w test_call.wav "Hello support, my name is Alex Jansen, account AC 7781, I cannot log in and need urgent help."
```

Windows alternatives:
- Use any existing `.wav`/`.mp3` file
- Or use browser recording from UI

## 9. Common Problems

1. `transcription.status = failed` with connection errors:
   - `docker compose ps transcriber`
   - `docker logs --tail 200 support-transcriber`
   - wait longer on first boot for model initialization

2. Caller fields still `Not mentioned`:
   - Use UI override inputs or `caller_name`/`account_or_reference`/`contact_info` in `/upload`

3. AI output weak or generic:
   - Verify Ollama reachable: `curl http://localhost:11434/api/tags`
   - Check formatter logs: `docker logs --tail 200 support-transcript-formatter`

4. No email visible:
   - verify `SMTP_HOST=mailpit` and `SMTP_PORT=1025` in `.env`
   - check `support-email-sender` logs

## 10. Useful Commands

```bash
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
| Transcriber Docs | http://localhost:9000/docs |
| n8n | http://localhost:5678 |
| Mailpit | http://localhost:8025 |
