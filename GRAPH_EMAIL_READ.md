# Microsoft Business Account and Entra App Registration Setup

## Purpose

This section explains how to:

1. create or access the Microsoft 365 business sandbox account
2. create the Microsoft Entra application
3. configure Microsoft Graph permissions
4. enable device login flow for local development

This setup is required for the email-monitor service to access Outlook mailboxes through Microsoft Graph.

---

# 1. Microsoft 365 Business Sandbox

A Microsoft 365 Business sandbox tenant is used because Microsoft Graph mailbox APIs require a real Exchange Online mailbox.

Example sandbox tenant:

```text id="v2t9m1"
companyname.onmicrosoft.com
```

Example sandbox user:

```text id="4g4m0l"
Name@companyname.onmicrosoft.com
```

---

# 2. Create Microsoft 365 Sandbox Tenant

## Option A — Microsoft 365 Developer Program

Preferred for development/testing.

Join:

```text id="6u0z7v"
https://developer.microsoft.com/microsoft-365/dev-program
```

OR

## Option B — Microsoft 365 Business

Create a Microsoft 365 Business subscription.

This automatically provisions:

* Entra tenant
* Exchange Online mailbox
* Microsoft Graph access

---

# 3. Access Microsoft Entra Admin Center

Open:

```
https://entra.microsoft.com
```

Sign in using the sandbox admin account.

Example:

```
Name@companyname.onmicrosoft.com
```

---

# 4. Create App Registration

Navigate to:

```text id="prl61n"
Applications
→ App registrations
→ New registration
```

---

# 5. Configure App Registration

## Name

Example:

```
Email Monitor
```

---

## Supported account types

Recommended:

```
Accounts in this organizational directory only
(Single tenant)
```

For multi-organization support later, this can be changed to:

```
Accounts in any organizational directory
(Multitenant)
```

---

# 6. Save Important Values

After creation, copy:

## Application (client) ID

```
CLIENT_ID
```

## Directory (tenant) ID

```
TENANT_ID
```

These values go into `.env`.

---

# 7. Enable Device Login Flow

Navigate to:

```
Authentication
→ Add platform
→ Mobile and desktop applications
```

Enable:

```
https://login.microsoftonline.com/common/oauth2/nativeclient
```

This is required for:

```
PublicClientApplication(...)
```

and device-code authentication.

---

# 8. Configure Microsoft Graph Permissions

Navigate to:

```text id="gk4x3o"
API permissions
→ Add permission
→ Microsoft Graph
→ Delegated permissions
```

Add:

```text id="g84q8s"
Mail.Read
User.Read
```

**Note:** `Mail.Read` includes full permissions to read email attachments (metadata, download content, etc.). No additional attachment-specific permissions are needed.

---

# 9. Grant Admin Consent

Still in API permissions:

Click:

```
Grant admin consent
```

This allows users in the tenant to authenticate successfully.

---

# 10. Configure `.env`

Example:

```
CLIENT_ID=<APPLICATION_CLIENT_ID>
TENANT_ID=<DIRECTORY_TENANT_ID>

OLLAMA_URL=http://ollama:11434
OLLAMA_MODEL=llama3.1:8b
VOICE_APP_URL=http://voice-app:5000
```

---

# 11. Test Authentication

Start services:

```
docker compose up --build
```

The logs should show:

```
To sign in, use a web browser to open:
https://login.microsoft.com/device
```

Authenticate using the sandbox business account.

Example:

```
Name@companyname.onmicrosoft.com
```

---

# 12. Successful Result

Successful mailbox access should produce:

```
GRAPH STATUS: 200
```

and:

```
Processing X emails
```

This confirms:

* Entra authentication works
* Exchange mailbox exists
* Graph API access works
* sandbox environment is correctly provisioned
