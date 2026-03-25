# Customer Support Call Transcription & Incident Form System

Local-first support-call pipeline with Docker Compose:
- Transcribe call audio (Whisper service)
- Extract structured incident fields (local Ollama via formatter)
- Send notification email
- Store completed forms in PostgreSQL

This repo now supports both:
- Browser UI demo flow at `http://localhost:5000`
- Direct API/terminal flow via `curl`

## Architecture

```
Audio file / Browser recording
                                        |
                                        v
Voice App (:5000)
        - validates audio
        - sends to Transcriber
        - sends transcript to Formatter
        - sends email
        - stores form in DB
                                        |
                                        +--> Transcriber (:9000, /asr)
                                        +--> Transcript Formatter (:5001, /format)
                                        +--> Email Sender (:5002, /send)
                                        +--> PostgreSQL (:5432)
```

Mailpit (`:8025`) is included in `dev` profile for local email inbox preview.

## Services

| Service | Container | Port | Purpose |
|---|---|---|---|
| `database` | `support-db` | 5432 | Incident form persistence |
| `n8n` | `support-n8n` | 5678 | Optional workflow orchestration |
| `voice-app` | `support-voice-app` | 5000 | UI + `/upload` API |
| `transcriber` | `support-transcriber` | 9000 | Whisper ASR endpoint |
| `transcript-formatter` | `support-transcript-formatter` | 5001 | Local AI form filling |
| `email-sender` | `support-email-sender` | 5002 | SMTP dispatch |
| `mailpit` (`dev`) | `support-mailpit` | 8025 | Local test inbox |

## Prerequisites

- Docker Desktop (Windows/macOS) or Docker Engine + Compose plugin (Linux)
- Ollama installed on host and running on `localhost:11434`
- One pulled model (default: `llama3.1:8b`)

### Install Ollama

Linux/macOS:

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.1:8b
```

Windows (PowerShell):

```powershell
winget install Ollama.Ollama
ollama pull llama3.1:8b
```

## Quick Start (All OS)

1. Clone repo and open folder.
2. Copy `.env.example` to `.env` and adjust values if needed.
3. Start services.

Linux/macOS:

```bash
docker compose --profile dev up -d --build
```

Windows PowerShell:

```powershell
docker compose --profile dev up -d --build
```

4. Wait until core services are healthy:

```bash
docker compose ps
```

5. Open UI:

`http://localhost:5000`

## Using The Demo UI

At `http://localhost:5000`:
- Option A: upload an existing audio file
- Option B: record in browser and send recording
- Optional caller overrides:
        - Caller name
        - Account/reference
        - Contact info

Those override fields are sent to formatter metadata and used to reliably populate caller information when needed.

## API Usage

### Upload endpoint

`POST /upload` (`multipart/form-data`)

Required:
- `file`

Optional:
- `caller_name`
- `account_or_reference`
- `contact_info`

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

### List forms

```bash
curl -sS http://localhost:5000/forms | python3 -m json.tool
```

## Configuration

Important variables from `.env`:

| Variable | Default | Used by |
|---|---|---|
| `POSTGRES_USER` | `support` | DB/Voice app |
| `POSTGRES_PASSWORD` | `support_secret` | DB/Voice app |
| `POSTGRES_DB` | `support_db` | DB/Voice app |
| `SUPPORT_EMAIL` | `support-team@example.com` | Voice app |
| `SMTP_HOST` | `mailpit` | Email sender |
| `SMTP_PORT` | `1025` | Email sender |
| `OLLAMA_MODEL` | `llama3.1:8b` | Formatter |
| `WHISPER_MODEL` | `small` | Transcriber |

## Cross-Platform Notes

- Linux: if Ollama is a systemd service, ensure it is running before `docker compose up`.
- macOS: Docker Desktop + Ollama app is sufficient.
- Windows: run commands in PowerShell; use `curl.exe` to avoid PowerShell alias behavior.
- Browser recording requires microphone permission and HTTPS is not required for `localhost`.

## Troubleshooting

1. Transcription fails with connection error:
         - Check `support-transcriber` status: `docker compose ps transcriber`
         - Check logs: `docker logs --tail 200 support-transcriber`
         - First startup can take time while model initializes/downloads.

2. Caller fields still show `Not mentioned`:
         - Use override inputs in UI or pass optional form fields to `/upload`.

3. AI extraction looks generic:
         - Check formatter logs: `docker logs --tail 200 support-transcript-formatter`
         - Confirm Ollama is reachable on host: `curl http://localhost:11434/api/tags`

4. No email in inbox:
         - Open Mailpit at `http://localhost:8025`
         - Verify SMTP vars in `.env` match Mailpit defaults for local dev.

## Stop / Reset

Stop services:

```bash
docker compose --profile dev down
```

Stop and wipe volumes:

```bash
docker compose --profile dev down -v
```

## Additional Test Guide

See [TESTING.md](TESTING.md) for detailed validation scenarios.
