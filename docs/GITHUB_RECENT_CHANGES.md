# Email integration — branch summary

Work on inbound email support for the Repak AI calling assistant (NHL Stenden project team).

---

## Branch

| Item | Value |
|------|--------|
| Feature branch | `feature/email-integration` |
| Base branch | `feat/email-attachment-retrieval` |
| Author | Thijs Thiery (`thijs.thiery@student.nhlstenden.com`) |

Graph and email-monitor groundwork on the base branch: Fyodor Smorodin (`fjodor.smorodins@student.nhlstenden.com`).

---

## Goal

Inbound support email uses the same pipeline as a phone call:

```
mailbox → email-monitor → voice-app → transcript-formatter → incident form → notification
```

Email skips transcription (Whisper); the message body is already text.

---

## Changes on `feature/email-integration`

### voice-app

- `POST /ingest/email` — accept email JSON, classify, format, store
- `voice-app/classifier.py` — `support` / `not_support` / `unclear` before case creation
- Metadata `source_channel: outlook` on formatted incidents

### email-monitor

- Persisted deduplication (`processed_store.py`) and support-address filter
- Forward new mail to `voice-app` via `POST /ingest/email`
- `POST /sync` for manual inbox polling
- Mailbox access via `GRAPH_AUTH_MODE`:
  - **Graph** — `personal` or `device` (Microsoft Graph, device login)
  - **IMAP** — Gmail or Outlook.com (app password)

### Auth and configuration

- `email-monitor/graph_auth.py` — `personal`, `device`, `application`
- `email-monitor/imap_client.py` — configurable IMAP host (e.g. `imap.gmail.com`)
- `.env.example` — variables for Graph and IMAP

### Testing

- `scripts/test-email-ingest.ps1` — smoke test without a live mailbox
- `scripts/demo-outlook-ingest.ps1` — trigger live inbox sync
- `docker-compose.yml` — `env_file: .env` on `email-monitor`

### Documentation

- `docs/EMAIL_INGEST_SETUP.md` — mailbox connection for local development
- `email-monitor/TESTING_AT_HOME.md` — pointer to the setup guide

---

## Commits

| Commit | Area |
|--------|------|
| `chore: add Graph/IMAP auth and Docker email-test stack` | Initial stack |
| `feat(ISR-241): persist new-email detection and support inbox filter` | Detection |
| `feat(ISR-242): wire email-monitor to voice-app ingest` | Monitor → voice-app |
| `feat(ISR-243): add email ingest route without transcription` | voice-app ingest |
| `feat(ISR-311): classify inbound email before case creation` | Classifier |
| `feat(ISR-303): support Gmail IMAP and Outlook Graph personal auth` | Dual auth |
| `chore(ISR-242): load email-monitor secrets from .env in compose` | Docker wiring |
| `feat(ISR-241): add POST /sync for on-demand inbox polling` | Manual sync |
| `test(ISR-245): add synthetic and live email ingest demo scripts` | Demo scripts |

Commit messages reference ISR board tickets (US-40 / US-26).

---

## Compare on GitHub

- Base: https://github.com/AlexMakesC0de/AI-calling-assistant/tree/feat/email-attachment-retrieval
- Diff: https://github.com/AlexMakesC0de/AI-calling-assistant/compare/feat/email-attachment-retrieval...feature/email-integration

---

## Known limitations

| Topic | Notes |
|-------|--------|
| Personal Outlook via Graph | Entra app registration and device login required |
| Gmail | `GRAPH_AUTH_MODE=imap` with a Google app password |
| HTML in marketing mail | IMAP may pass raw HTML to the classifier; use plain-text test mail for demos |
| Database on email ingest | `transcriptchunk` relation missing in some environments; form generation and Mailpit still work |
| Client production mailbox | `GRAPH_AUTH_MODE=application` with tenant admin (client IT) |

---

## Related documentation

- [EMAIL_INGEST_SETUP.md](EMAIL_INGEST_SETUP.md)
- [GRAPH_EMAIL_READ.md](../GRAPH_EMAIL_READ.md)
- [TESTING.md](../TESTING.md)
