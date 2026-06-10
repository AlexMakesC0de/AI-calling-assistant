# Dashboard

Next.js 15 + Prisma + shadcn/ui dashboard for the support call pipeline. Upload audio, browse AI-extracted incidents, search transcripts semantically, read the dispatch inbox (Mailpit), and watch service health.

## How this fits in the monorepo

- **Database:** shares `support-db` with the rest of the stack. SQL files in `../database/initDb/` are authoritative; Prisma here acts as a typed query client. **Never run `prisma migrate` against `support_db`** — it would try to re-own tables managed by the Python services.
- **Pipeline:** `/upload` posts audio to `voice-app:5000/upload`, which transcribes, fills the incident form, dispatches an email, and writes the result to the DB.
- **Mailpit:** `/inbox` reads the SMTP catch-all the email-sender ships into. The dashboard proxies messages, raw `.eml`, attachments, and an SSE stream so the browser stays same-origin.
- **Ollama:** `/search` embeds queries with `nomic-embed-text` and runs cosine search via pgvector against `transcriptchunk.embedding`.

## Pages

| Route | Purpose |
|---|---|
| `/` | Overview — incident counts, sentiment distribution, recent incidents, recent inbox |
| `/upload` | Drop audio → run the AI pipeline |
| `/incidents` | Filterable list of AI-extracted forms |
| `/incidents/[id]` | Full form view with caller / issue / resolution / follow-up, summary (en + nl), transcript, raw JSON tree, dispatched-email cross-link, **Word export** |
| `/inbox` | Mailpit list with full-text search, qualifier syntax, tag chips, bulk read/delete, live updates |
| `/inbox/[id]` | Email detail — headers, attachments, raw `.eml`, HTML iframe, incident cross-link |
| `/inbox/outlook` | Outlook (Microsoft 365) tab — same UX, reads a shared mailbox via Graph API |
| `/inbox/outlook/[id]` | Outlook detail — headers, attachments, HTML body, incident cross-link, deep-link to outlook.com |
| `/search` | Semantic search over transcript chunks with on-demand backfill |
| `/system` | Live service health with first-load-of-the-day fill animation |

## Setup (Docker — recommended)

```bash
# From the repo root
cp .env.example .env
docker compose up -d dashboard
# → http://localhost:3000
```

The compose service `dashboard` overrides `DATABASE_URL`, `VOICE_APP_UPLOAD_URL`, and `MAILPIT_URL` to in-network values automatically.

## Setup (host dev — for hot reload)

```bash
# 1. Make sure the supporting services are up
docker compose --profile dev up -d database voice-app transcriber transcript-formatter email-sender mailpit ollama

# 2. Install deps + generate Prisma client
cd dashboard
npm install

# 3. Configure env
cp .env.example .env

# 4. Run it
npm run dev
# → http://localhost:3000
```

## Semantic search setup

The first time you use `/search`, the embed model needs to be present in Ollama and existing chunks need vectors:

```bash
# Pull the embed model into the running ollama container
docker exec -it support-ollama ollama pull nomic-embed-text

# (Optional) apply the embedding column migration to a pre-existing volume
docker exec -i support-db psql -U support -d support_db < ../database/initDb/03_chunk_embeddings.sql
```

Then open `/search` and click **Backfill embeddings**. The action embeds 50 chunks at a time and reports remaining count.

## Outlook setup (optional)

The Outlook tab uses Microsoft Graph with **client-credentials** flow — no per-user OAuth, just an app registration that reads a shared mailbox on behalf of nobody.

1. Register an app in Azure AD (App registrations → New registration).
2. **API permissions → Microsoft Graph → Application permissions**: add `Mail.Read` (and optionally `Mail.ReadWrite`). Click **Grant admin consent**.
3. **Certificates & secrets → New client secret**, copy the value.
4. Set the env vars on the dashboard service:

```bash
OUTLOOK_TENANT_ID=<your tenant id or domain>
OUTLOOK_CLIENT_ID=<app's application (client) id>
OUTLOOK_CLIENT_SECRET=<the secret value>
OUTLOOK_MAILBOX=support@yourcompany.com
OUTLOOK_FOLDER=Inbox            # well-known name or folder id
```

Restart the dashboard. The Outlook tab in `/inbox` lights up. If the variables are missing, the tab still appears with a setup-instructions card.

## Mailpit search qualifiers

The inbox search bar accepts Mailpit's qualifier syntax:

- `from:support@example.com`
- `to:user@example.com`
- `subject:"Incident Form"`
- `tag:billing`
- `is:unread`
- `has:attachment`

Click any tag chip below the search box to filter to that tag.

## Design system

`app/globals.css` defines a strict black/white palette via shadcn CSS variables. Cards have flat 1px borders, no shadows. Status uses bar fills + iconography rather than colored states.

## Tech notes

- **Server actions** drive all mutations (upload, mark read, delete, tag, backfill embeddings).
- **SSE** at `/api/inbox/stream` polls Mailpit every 3s and pushes a tick when totals change. The inbox client refreshes the list on each tick — the WebSocket route is stand-alone and doesn't require Mailpit's native WS.
- **pgvector** queries use `Prisma.sql` with raw vector literals (`'[...]'::vector`) since the embedding column is unsupported by Prisma's typed query API.
- **Word export** at `/api/incidents/[id]/docx` builds a `.docx` server-side via the `docx` package.
