# Email ingest setup guide

This guide explains how a team member can connect a mailbox to the Repak email pipeline for local development and demos.

**Maintainer:** Thijs Thiery (`thijs.thiery@student.nhlstenden.com`)

---

## Overview

The `email-monitor` service (port **5003**) reads new messages from a mailbox and forwards them to `voice-app` (port **5000**), which classifies the content, builds an incident form, and sends a notification (Mailpit in local dev).

Authentication is selected with **`GRAPH_AUTH_MODE`** in `.env`:

| Mode | Mailbox type | Typical use |
|------|----------------|-------------|
| `imap` | Gmail, Outlook.com | Local development |
| `personal` | @outlook.com / @hotmail.com | Graph + device login |
| `device` | School or dev tenant (`*.onmicrosoft.com`) | Graph + device login |
| `application` | Client shared mailbox | Production (requires admin + secret) |

Only one mode is active at a time.

---

## Prerequisites

1. Clone the repository and check out `feature/email-integration` (or the current email integration branch).
2. Copy `.env.example` to `.env` (never commit `.env`).
3. Start the stack:

```powershell
docker compose --profile dev up -d
```

4. Pull the Ollama model once:

```powershell
docker exec support-ollama ollama pull llama3.1:8b
```

---

## Option A — Gmail (IMAP)

Recommended when the support mailbox is a **@gmail.com** address.

### 1. Enable IMAP in Gmail

Gmail → **Settings** → **See all settings** → **Forwarding and POP/IMAP** → **Enable IMAP**.

### 2. Create a Google app password

1. Enable 2-Step Verification on the Google account.
2. Open https://myaccount.google.com/apppasswords
3. Create a password (e.g. name: `RepakDev`).
4. Copy the 16-character value.

### 3. Configure `.env`

```env
GRAPH_AUTH_MODE=imap
GRAPH_MAILBOX=your.name@gmail.com
SUPPORT_INBOX_ADDRESSES=your.name@gmail.com
OUTLOOK_IMAP_HOST=imap.gmail.com
OUTLOOK_IMAP_PORT=993
OUTLOOK_IMAP_USER=your.name@gmail.com
OUTLOOK_IMAP_PASSWORD=your-google-app-password
EMAIL_ENABLE_BACKGROUND_SYNC=true
VOICE_APP_URL=http://voice-app:5000
```

### 4. Verify

```powershell
docker compose --profile dev up -d --force-recreate email-monitor
curl http://localhost:5003/health/imap
```

Expected: `"ok": true`

---

## Option B — Outlook.com (Graph personal)

Recommended for **@outlook.com** / **@hotmail.com** mailboxes without a paid M365 tenant.

### 1. Register an Entra application

1. Sign in at https://entra.microsoft.com
2. **App registrations** → **New registration**
3. Name: e.g. `Repak Email Dev`
4. Supported account types: **Accounts in any organizational directory and personal Microsoft accounts**
5. Copy the **Application (client) ID**

### 2. Configure the app

- **Authentication** → add platform **Mobile and desktop applications** → enable  
  `https://login.microsoftonline.com/common/oauth2/nativeclient`
- Set **Allow public client flows** to **Yes**
- **API permissions** → Microsoft Graph → Delegated: `Mail.Read`, `User.Read`
- Grant admin consent if the button is available

### 3. Configure `.env`

```env
GRAPH_AUTH_MODE=personal
GRAPH_CLIENT_ID=your-application-client-id
GRAPH_MAILBOX=your.name@outlook.com
SUPPORT_INBOX_ADDRESSES=your.name@outlook.com
EMAIL_ENABLE_BACKGROUND_SYNC=true
```

Do **not** set `GRAPH_TENANT_ID` for `personal` mode.

### 4. Device login

```powershell
docker compose --profile dev up -d --force-recreate email-monitor
docker logs -f support-email-monitor
```

When a device code appears, open https://microsoft.com/devicelogin and sign in with the **same Outlook account** as `GRAPH_MAILBOX`.

### 5. Verify

```powershell
curl http://localhost:5003/health/graph
```

---

## Option C — School / dev tenant (Graph device)

Use when the mailbox lives in an Azure AD tenant (e.g. `name@school.onmicrosoft.com`).

```env
GRAPH_AUTH_MODE=device
GRAPH_CLIENT_ID=your-application-client-id
GRAPH_TENANT_ID=your-directory-tenant-id
GRAPH_MAILBOX=name@school.onmicrosoft.com
SUPPORT_INBOX_ADDRESSES=name@school.onmicrosoft.com
```

The account must have an **Exchange Online mailbox**. Entra ID alone (no mail license) is not sufficient.

Device login and verification steps are the same as Option B.

---

## Option D — Client production (Graph application)

For a factory shared support mailbox. Requires client IT: app registration, client secret, admin consent, and `Mail.Read` application permission.

```env
GRAPH_AUTH_MODE=application
GRAPH_CLIENT_ID=...
GRAPH_TENANT_ID=...
GRAPH_CLIENT_SECRET=...
GRAPH_MAILBOX=support@clientdomain.com
```

See [GRAPH_EMAIL_READ.md](../GRAPH_EMAIL_READ.md) for Entra details.

---

## Running a demo

### Synthetic test (no mailbox)

```powershell
.\scripts\test-email-ingest.ps1
```

Confirms classifier, formatter, and Mailpit without external email.

### Live mailbox test

1. Send a **plain-text** support-style email to the configured mailbox (unread).
2. Trigger sync:

```powershell
.\scripts\demo-outlook-ingest.ps1
```

3. Open Mailpit: http://localhost:8025

### Re-process mail for a repeated demo

```powershell
Remove-Item ".\local-storage\email-monitor\processed_message_ids.json" -ErrorAction SilentlyContinue
docker restart support-email-monitor
```

Then send a **new** test message.

---

## Health endpoints

| URL | When |
|-----|------|
| `GET http://localhost:5003/health` | Service up |
| `GET http://localhost:5003/health/imap` | `GRAPH_AUTH_MODE=imap` |
| `GET http://localhost:5003/health/graph` | Graph modes |
| `POST http://localhost:5003/sync` | Run one inbox poll immediately |

---

## Troubleshooting

| Symptom | Likely cause | Action |
|---------|----------------|--------|
| IMAP `AUTHENTICATE failed` | Wrong password or IMAP disabled | Use app password; enable IMAP |
| Graph `AADSTS9002332` | App not allowing personal accounts | Fix supported account types in Entra |
| Graph `401` on inbox | No Exchange mailbox on tenant user | Use IMAP or a licensed mailbox |
| `Processing 0 emails` | No unread mail, or already processed | Send new unread mail; clear processed store |
| Classifier reads HTML/CSS | Marketing email HTML in body | Use plain-text test mail for demos |
| voice-app timeout | Ollama slow on first run | Wait; re-run `POST /sync` |

---

## Security notes

- Never commit `.env` or app passwords.
- Revoke and recreate app passwords if they are exposed.
- Use separate test mailboxes for development; do not use production client credentials on student laptops.

---

## Related documentation

- [GITHUB_RECENT_CHANGES.md](GITHUB_RECENT_CHANGES.md)
- [GRAPH_EMAIL_READ.md](../GRAPH_EMAIL_READ.md)
