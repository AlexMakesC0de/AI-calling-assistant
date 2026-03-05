# Testing Guide

This guide walks you through testing the **Customer Support Call Transcription
& Reporting System**.

## How the application works

```
You upload a recorded support call (audio file)
        │
        ▼
  ┌─────────────┐
  │  Voice App  │  Saves the file
  │  (port 5000)│
  └──────┬──────┘
         │  automatically sends to...
         ▼
  ┌─────────────┐
  │   Whisper   │  Converts speech to text (transcription)
  │  (port 9000)│
  └──────┬──────┘
         │  transcript text goes to...
         ▼
  ┌─────────────────┐
  │   Transcript    │  AI reads the transcript and fills out
  │   Formatter     │  an incident form (extracts caller info,
  │  (port 5001)    │  issue, resolution, follow-up, etc.)
  └──────┬──────────┘
         │  completed form goes to...
         ▼
  ┌─────────────┐
  │ Email Sender│  Sends the completed form to the
  │ (port 5002) │  support team email address
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │   Mailpit   │  Catches the email locally (dev mode)
  │  (port 8025)│  Open http://localhost:8025 to read it
  └─────────────┘
```

**The entire pipeline is automatic.** You just upload an audio file and
everything happens on its own. At the end, the support team gets an email
with the completed incident form.

---

## Prerequisites

Before testing, make sure:

1. **Docker is running** — all containers should be started:
   ```bash
   docker compose --profile dev up -d --build
   ```

2. **Ollama is running** on your machine (the AI that fills the form):
   ```bash
   systemctl status ollama     # should be "active (running)"
   ollama list                 # should include llama3.2:1b
   ```

3. **All containers are healthy:**
   ```bash
   docker compose --profile dev ps
   ```
   You should see 7 containers, all with status **Up (healthy)**.

---

## Test 1: Quick health check

Verify each service is responding:

```bash
curl -s http://localhost:5000/health    # Voice App
curl -s http://localhost:5001/health    # Transcript Formatter
curl -s http://localhost:5002/health    # Email Sender
```

Each should return: `{"status": "ok"}`

---

## Test 2: Upload a recorded call (full pipeline)

This is the main test. You upload an audio file and the system does
everything automatically.

### Step 1: Get an audio file

You need a `.wav` or `.mp3` file of a support call. For testing, you can:

**Option A** — Record yourself reading a sample conversation:
```bash
# Records for 15 seconds from your microphone
arecord -d 15 -f cd test_call.wav
```

**Option B** — Generate synthetic speech with a sample conversation:
```bash
espeak-ng -w test_call.wav "Hello, thank you for calling tech support. My name is Sarah. How can I help you? Hi Sarah, my laptop keeps crashing. It says critical process died with a blue screen. That sounds like a blue screen issue. Boot into safe mode and run SFC scan now. Okay it found corrupted files and repaired them. It works now, thank you so much."
```

**Option C** — Use any `.wav` or `.mp3` file you already have.

### Step 2: Upload the file

```bash
curl -s -X POST http://localhost:5000/upload \
  -F "file=@test_call.wav" | python3 -m json.tool
```

### Step 3: Wait for the pipeline

The system will:
1. Transcribe the audio (Whisper) — takes a few seconds
2. Fill out the incident form (AI) — takes 10-30 seconds on first run
3. Send the email — instant

You'll get a JSON response showing the status of each step.

### Step 4: Check the email

Open **http://localhost:8025** in your browser.

You should see an email with:
- **Subject:** `Incident Form Completed – [form-id] [Category]`
- **Body:** The completed incident form with all fields filled in:
  - Caller information (name, account, contact)
  - Call details (date, agent, duration)
  - Issue (category, priority, description, error messages)
  - Resolution (status, steps taken, outcome)
  - Follow-up (required?, actions, department)
  - Customer sentiment
  - Call summary
  - Full transcript

---

## Test 3: Test just the AI form-filler

If you want to test the AI form-filling without uploading audio (skip the
Whisper step), you can send a transcript directly:

```bash
curl -s -X POST http://localhost:5001/format \
  -H "Content-Type: application/json" \
  -d '{
    "transcript": "Agent: Hello, thank you for calling TechSupport. My name is Sarah. How can I help you today? Caller: Hi Sarah, my laptop keeps crashing whenever I try to open my email client. It started happening after the last Windows update. Agent: I understand how frustrating that must be. Can you tell me the exact error message you see? Caller: It says something like critical process died with a blue screen. Agent: That sounds like a BSOD issue. Let me walk you through a fix. First, can you boot into Safe Mode? Caller: Yes, I can do that. Agent: Great. Once in Safe Mode, open Command Prompt as administrator and run sfc scannow. Caller: Okay, it is running now. It found some corrupted files and repaired them. Agent: Perfect. Please restart normally and try opening your email client again. Caller: It works now! Thank you so much, Sarah. Agent: You are welcome! Is there anything else I can help with? Caller: No, that is all. Thanks again. Agent: Have a great day! Goodbye."
  }' | python3 -m json.tool
```

You should see a completed incident form with fields like:
- `issue.category`: "Technical"
- `issue.priority`: "High"
- `resolution.status`: "Resolved"
- `resolution.steps_taken`: ["Boot into Safe Mode", "Run sfc scannow"]
- etc.

---

## Test 4: Test just the email sender

Send a test email to verify Mailpit catches it:

```bash
curl -s -X POST http://localhost:5002/send \
  -H "Content-Type: application/json" \
  -d '{
    "to": "support@example.com",
    "subject": "Test Email",
    "body": "This is a test email from the support system."
  }' | python3 -m json.tool
```

Expected: `{"status": "sent", "to": "support@example.com"}`

Check **http://localhost:8025** to see the email.

---

## Test 5: Use the automated test script

There's a script that runs the full pipeline for you:

```bash
./test_pipeline.sh test_call.wav
```

It uploads the file, waits for the pipeline to complete, and tells you
whether everything succeeded.

---

## What the incident form looks like

When the AI fills out the form, the email contains something like this:

```
═══ FORM ID: 4d2d7854-2b0d-45eb-b546-d463c1ad0fc8 ═══

CALLER INFORMATION
  Name:      Sarah
  Account:   Not mentioned
  Contact:   Not mentioned

CALL DETAILS
  Date:      2026-03-05T00:00:00+00:00
  Agent:     Not mentioned
  Duration:  ~1 minute

ISSUE
  Category:  Technical
  Priority:  High
  Description: Laptop keeps crashing after Windows update,
               blue screen issue with corrupted files.
  Error messages: Critical process died with blue screen

RESOLUTION
  Status:    Resolved
  Steps taken:
  - Boot into Safe Mode
  - Run sfc /scannow
  Outcome:   Works now

FOLLOW-UP
  Required:  No

CUSTOMER SENTIMENT: Satisfied

SUMMARY
Laptop was crashing due to corrupted system files after a Windows update.
Agent guided caller through SFC scan in Safe Mode which repaired the files.
Issue resolved successfully.
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Container is unhealthy | `docker compose logs <container-name>` |
| Whisper takes long to start | First boot downloads the model (~140 MB). Wait 60s |
| AI returns basic/wrong form | Check if Ollama is running: `systemctl status ollama` |
| First AI request is slow (30s) | Normal — Ollama loads the model into memory on first request |
| Email not showing in Mailpit | Make sure `.env` has `SMTP_HOST=mailpit` and `SMTP_PORT=1025`, then rebuild: `docker compose --profile dev up -d --build email-sender` |
| Pipeline hangs | Check voice-app logs: `docker compose logs support-voice-app` |
| Empty transcript | The audio might be too quiet or silent. Use a clearer recording |

### Useful commands

```bash
# See logs for any service
docker compose logs -f support-voice-app
docker compose logs -f support-transcript-formatter
docker compose logs -f support-email-sender

# Restart a service
docker compose restart support-voice-app

# Rebuild everything
docker compose --profile dev down && docker compose --profile dev up -d --build

# Check Ollama
ollama list
systemctl status ollama
```

---

## Service URLs

| Service | URL | Purpose |
|---------|-----|---------|
| Voice App | http://localhost:5000 | Upload audio files |
| Transcript Formatter | http://localhost:5001 | AI form-filler |
| Email Sender | http://localhost:5002 | Send emails |
| Whisper API | http://localhost:9000/docs | Speech-to-text engine |
| n8n Workflows | http://localhost:5678 | Visual workflow editor |
| Mailpit Inbox | http://localhost:8025 | View caught emails |
