// Voice-app upload endpoint. In-network: http://voice-app:5000/upload.
// Host dev: http://localhost:5000/upload.
// Mailpit base URL. In-network: http://mailpit:8025. Host dev: http://localhost:8025.
const mailpitBaseUrl = (process.env.MAILPIT_URL ?? "http://localhost:8025").replace(/\/$/, "");

const ollamaBaseUrl = (process.env.OLLAMA_URL ?? "http://localhost:11434").replace(/\/$/, "");

const outlookTenantId = process.env.OUTLOOK_TENANT_ID ?? "";
const outlookClientId = process.env.OUTLOOK_CLIENT_ID ?? "";
const outlookClientSecret = process.env.OUTLOOK_CLIENT_SECRET ?? "";
const outlookMailbox = process.env.OUTLOOK_MAILBOX ?? "";
const outlookFolder = process.env.OUTLOOK_FOLDER ?? "Inbox";

export const env = {
  voiceAppUploadUrl: process.env.VOICE_APP_UPLOAD_URL ?? "http://localhost:5000/upload",
  mailpitBaseUrl,
  ollamaBaseUrl,
  ollamaEmbedModel: process.env.OLLAMA_EMBED_MODEL ?? "nomic-embed-text",
  // Microsoft Graph (Outlook) — client-credentials flow against a shared
  // mailbox. The dashboard never asks the user to sign in; it just reads
  // mail on the configured mailbox using app-only permissions
  // (Mail.Read application permission, admin-consented).
  outlook: {
    tenantId: outlookTenantId,
    clientId: outlookClientId,
    clientSecret: outlookClientSecret,
    mailbox: outlookMailbox,
    folder: outlookFolder,
    configured: Boolean(outlookTenantId && outlookClientId && outlookClientSecret && outlookMailbox),
  },
  // Service health endpoints. Defaults match host-mode dev (services exposed
  // on localhost via docker-compose port mappings). Override per-service when
  // running outside docker-compose or behind a reverse proxy.
  serviceHealth: {
    voiceApp: process.env.VOICE_APP_HEALTH_URL ?? "http://localhost:5000/health",
    transcriber: process.env.TRANSCRIBER_HEALTH_URL ?? "http://localhost:9000/health",
    formatter: process.env.FORMATTER_HEALTH_URL ?? "http://localhost:5001/health",
    email: process.env.EMAIL_HEALTH_URL ?? "http://localhost:5002/health",
    mailpit: process.env.MAILPIT_HEALTH_URL ?? `${mailpitBaseUrl}/api/v1/info`,
    telephony: process.env.TELEPHONY_HEALTH_URL ?? "http://localhost:5010/health",
    ollama: process.env.OLLAMA_HEALTH_URL ?? `${ollamaBaseUrl}/api/version`,
  },
};
