# Customer Support Call Transcription & Incident Form System

A fully local, Docker Compose–orchestrated pipeline that takes **recorded
customer support calls**, **transcribes** them with **speaker diarization**
(identifies who said what), uses an **AI (Ollama)** to automatically fill out
an **incident form**, and **emails** the completed form to the support team.

The transcriber uses **faster-whisper** for speech-to-text with word-level
timestamps, combined with **speechbrain ECAPA-TDNN** speaker embeddings and
**spectral clustering** to separate speakers (e.g. Agent vs Caller).

The entire pipeline is automatic — upload an audio file and everything
happens on its own.

---

## How It Works

```
  Recorded support call (.wav / .mp3)
          │
          ▼
  ┌───────────────┐
  │   Voice App   │  Validates & saves the audio file
  │  (port 5000)  │
  └───────┬───────┘
          │ sends audio to...
          ▼
  ┌───────────────┐
  │  Transcriber  │  Speech-to-text (faster-whisper) with
  │  (port 9000)  │  speaker diarization (speechbrain)
  └───────┬───────┘
          │ diarized transcript goes to...
          ▼
  ┌───────────────────┐
  │    Transcript     │  AI reads the transcript and fills out
  │    Formatter      │  a structured incident form (extracts
  │   (port 5001)     │  caller info, issue, resolution, etc.)
  └───────┬───────────┘  Also rates confidence for each field.
          │ completed form goes to...
          ├──────────────────────┐
          ▼                      ▼
  ┌───────────────┐    ┌────────────────┐
  │  Email Sender │    │   PostgreSQL   │
  │  (port 5002)  │    │  (port 5432)   │
  └───────┬───────┘    └────────────────┘
          │              Form stored for
          ▼              future retrieval
  ┌───────────────┐
  │    Mailpit    │  Catches email locally (dev mode)
  │  (port 8025)  │  or real SMTP in production
  └───────────────┘
```

---

## Services

| # | Service | Container | Port | Purpose |
|---|---------|-----------|------|---------|
| 1 | PostgreSQL 16 | `support-db` | 5432 | Stores n8n data + incident forms |
| 2 | n8n | `support-n8n` | 5678 | Workflow orchestration (optional) |
| 3 | Voice App | `support-voice-app` | 5000 | Upload audio, runs full pipeline |
| 4 | Transcriber | `support-transcriber` | 9000 | Speech-to-text + speaker diarization |
| 5 | Transcript Formatter | `support-transcript-formatter` | 5001 | AI-powered incident form filler |
| 6 | Email Sender | `support-email-sender` | 5002 | SMTP email dispatch |
| 7 | Mailpit (dev) | `support-mailpit` | 8025 | Local email catch-all |

> **Note:** Voice App and Transcript Formatter run with `network_mode: host`
> so they can reach each other and the host-installed Ollama on `localhost:11434`.

---

## Prerequisites

- **Docker Engine** ≥ 24.x with Docker Compose v2
- **Ollama** installed on the host with a model pulled
- **~10 GB RAM** free (Whisper + speechbrain models + Ollama LLM in memory)

### Ollama Setup

```bash
# Install Ollama (if not already)
curl -fsSL https://ollama.com/install.sh | sh

# Pull the model
ollama pull llama3.1:8b

# Ensure Ollama listens on all interfaces (needed for Docker)
sudo mkdir -p /etc/systemd/system/ollama.service.d
echo -e "[Service]\nEnvironment=OLLAMA_HOST=0.0.0.0" | \
  sudo tee /etc/systemd/system/ollama.service.d/override.conf
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

---

## Quick Start

```bash
# 1. Clone the repository
git clone <repo-url> && cd IT-2C

# 2. Configure environment (or use the defaults)
#    Edit .env to set your own SMTP credentials, passwords, etc.

# 3. Build & launch all services (with Mailpit for dev)
docker compose --profile dev up -d --build

# 4. Verify everything is healthy
docker compose --profile dev ps
# All 7 containers should show "Up (healthy)"

# 5. Upload a test audio file
curl -s -X POST http://localhost:5000/upload \
  -F "file=@your_call_recording.wav" | python3 -m json.tool

# 6. Check the email at http://localhost:8025
```

---

## Features

### Automatic Pipeline
Upload an audio file and the system automatically:
1. **Validates** the file (format, size, MIME type)
2. **Classifies** the call opening (service vs personal) to avoid unnecessary processing
3. **Transcribes** service calls via faster-whisper with **speaker diarization**
4. **AI fills** the incident form — speaker labels help identify agent vs caller
5. **Emails** the completed form to the support team
6. **Stores** the form in PostgreSQL for records

### Multi-Language Support
The transcriber auto-detects spoken language and includes:
- `detected_language` (e.g. `en`, `nl`)
- `language_probability` (confidence score)

This metadata is passed through the pipeline and added to form metadata.

### Automatic Call Filtering (ISR-74)
Before full processing, the voice app runs a call gate:
- Uses optional telephony metadata (`call_type_signal`) when available
- Otherwise transcribes only the opening window and checks service declaration/intent
- Personal calls are skipped automatically (no formatter/email/database write)

This keeps the system fully automated while reducing non-work processing.

### Speaker Diarization
The transcriber identifies different speakers in the audio and labels each
line of the transcript (e.g. "Speaker 1: ...", "Speaker 2: ..."). This helps
the AI accurately determine who is the support agent and who is the caller,
leading to better form-filling accuracy.

### AI Confidence Scoring
The AI rates its confidence ("high" / "medium" / "low") for every field
it fills. Low-confidence fields are flagged in the email so support staff
know which fields may need manual review.

### Retry Logic
All HTTP calls between services (Transcriber, Formatter, Email) have automatic
retry with exponential backoff (3 attempts). Temporary failures won't break
the pipeline.

### File Validation
Uploads are validated for:
- File extension (`.wav`, `.mp3`, `.ogg`, `.flac`, `.m4a`, `.webm`)
- File size (max 50 MB, configurable)
- MIME type (checks actual file content, not just the declared type)

### Database Storage
Every completed incident form is stored in PostgreSQL and can be retrieved
via the API:
- `GET /forms` — list all forms (with filtering by category/priority)
- `GET /forms/<form_id>` — get a single form with full data

---

## API Reference

### Voice App

#### `POST /upload`
Upload an audio file and run the full pipeline.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | form-data | yes | Audio file (.wav, .mp3, .ogg, .flac, .m4a, .webm) |
| `call_type_signal` | form-data | no | Optional upstream IVR signal: `service`/`personal`/`1`/`2` |

**Response:** Full pipeline result with transcription, incident form, email
status, database status, and confidence scores.

#### `GET /forms`
List stored incident forms.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 50 | Max results (max 500) |
| `category` | string | — | Filter by category |
| `priority` | string | — | Filter by priority |

#### `GET /forms/<form_id>`
Get a single incident form with full JSON data.

#### `GET /health`
Health check. Returns `{"status": "ok"}`.

### Transcript Formatter

#### `POST /format`
Send a transcript and get back a completed incident form.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `transcript` | string | yes | Raw transcript text |
| `call_date` | ISO-8601 | no | When the call occurred |
| `metadata` | object | no | Arbitrary key-value pairs |

**Response:** Completed incident form with AI-filled fields and per-field
confidence ratings.

### Email Sender

#### `POST /send`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `to` | email | yes | Recipient address |
| `subject` | string | yes | Email subject |
| `body` | string | yes | Email body (plain or HTML) |
| `html` | boolean | no | Treat body as HTML |
| `report` | object | no | JSON data appended inline |

---

## Directory Structure

```
IT-2C/
├── docker-compose.yml                # Orchestrates all services
├── .env                              # Environment variables (not committed)
├── .gitignore
├── TESTING.md                        # Step-by-step testing guide
├── test_pipeline.sh                  # Automated pipeline test script
│
├── voice-app/                        # Main entry point — audio upload + pipeline
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app.py
│   └── .dockerignore
│
├── transcriber/                      # Speech-to-text + speaker diarization
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app.py
│   └── .dockerignore
│
├── transcript-formatter/             # AI-powered incident form filler
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app.py
│   └── .dockerignore
│
├── email-sender/                     # SMTP email dispatch
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app.py
│   └── .dockerignore
│
├── templates/                        # Incident form schema
│   └── incident_form_schema.json
│
└── n8n-workflows/                    # Importable n8n workflows
    └── support_call_pipeline.json
```

---

## Environment Variables

All variables have sensible defaults. Override them in a `.env` file.

| Variable | Default | Service | Description |
|----------|---------|---------|-------------|
| `POSTGRES_USER` | `support` | database | DB username |
| `POSTGRES_PASSWORD` | `support_secret` | database | DB password |
| `POSTGRES_DB` | `support_db` | database | DB name |
| `N8N_USER` | `admin` | n8n | n8n login user |
| `N8N_PASSWORD` | `admin` | n8n | n8n login password |
| `TZ` | `Europe/Amsterdam` | n8n | Timezone |
| `SMTP_HOST` | `mailpit` | email-sender | SMTP server |
| `SMTP_PORT` | `1025` | email-sender | SMTP port |
| `SMTP_USER` | *(empty)* | email-sender | SMTP username |
| `SMTP_PASSWORD` | *(empty)* | email-sender | SMTP password |
| `SMTP_FROM` | `support@example.com` | email-sender | From address |
| `SMTP_USE_TLS` | `false` | email-sender | Enable STARTTLS |
| `SUPPORT_EMAIL` | `support-team@example.com` | voice-app | Where to send completed forms |
| `OLLAMA_MODEL` | `llama3.1:8b` | transcript-formatter | Ollama model for AI |
| `WHISPER_MODEL` | `small` | transcriber | Whisper model size (tiny/base/small/medium/large-v2/large-v3) |
| `MAX_FILE_SIZE_MB` | `50` | voice-app | Max upload size |
| `OPENING_WINDOW_SECONDS` | `20` | voice-app | Seconds used for opening intent classification |
| `SERVICE_DECLARATION_PHRASES` | built-in defaults | voice-app | Comma-separated service-call declaration phrases |

---

## Testing

See [TESTING.md](TESTING.md) for the full step-by-step testing guide.

Quick smoke test:

```bash
# Generate test audio
espeak-ng -w test_call.wav "Hello, thank you for calling tech support. My name is Sarah. How can I help you?"

# Upload and run the pipeline
curl -s -X POST http://localhost:5000/upload -F "file=@test_call.wav" | python3 -m json.tool

# Check email at http://localhost:8025
# Check stored forms
curl -s http://localhost:5000/forms | python3 -m json.tool
```

---

## Stopping / Cleanup

```bash
# Stop all containers (preserves data)
docker compose --profile dev down

# Stop and remove all data (full reset)
docker compose --profile dev down -v
```

---

## License

Internal project — SSM Repak, Year 2, Period 3.
