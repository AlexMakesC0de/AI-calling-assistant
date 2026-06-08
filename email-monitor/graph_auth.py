"""
Microsoft Graph authentication for Outlook / Exchange Online.

Supports:
- application: client-credentials for shared support mailbox (client production)
- personal: device login for @outlook.com / @hotmail.com (home testing, no M365 license)
- device: device login for organizational sandbox tenants
- imap: see imap_client.py (no Graph)
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import requests
from msal import ConfidentialClientApplication, PublicClientApplication

logger = logging.getLogger(__name__)

GRAPH_SCOPE_DEFAULT = ["https://graph.microsoft.com/.default"]
GRAPH_SCOPE_DELEGATED = ["Mail.Read", "User.Read"]
GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
# Personal @outlook.com with an app that allows org + personal accounts (signInAudience
# AzureADandPersonalMicrosoftAccount) must use /common — not /consumers (AADSTS9002332).
PERSONAL_AUTHORITY = "https://login.microsoftonline.com/common"
CONSUMERS_AUTHORITY = "https://login.microsoftonline.com/consumers"


class GraphAuthError(Exception):
    """Raised when Graph credentials are missing or token acquisition fails."""


def auth_mode() -> str:
    mode = os.getenv("GRAPH_AUTH_MODE", "imap").strip().lower()
    if mode == "imap":
        return "imap"
    if mode not in ("application", "device", "personal"):
        raise GraphAuthError(
            f"Invalid GRAPH_AUTH_MODE '{mode}'. "
            "Use application, personal, device, or imap."
        )
    return mode


def uses_graph() -> bool:
    return auth_mode() != "imap"


def tenant_id() -> str:
    value = (os.getenv("GRAPH_TENANT_ID") or os.getenv("TENANT_ID") or "").strip()
    if not value:
        raise GraphAuthError("GRAPH_TENANT_ID (or TENANT_ID) is required for device mode.")
    return value


def client_id() -> str:
    value = (os.getenv("GRAPH_CLIENT_ID") or os.getenv("CLIENT_ID") or "").strip()
    if not value:
        raise GraphAuthError("GRAPH_CLIENT_ID (or CLIENT_ID) is required.")
    return value


def client_secret() -> str:
    value = os.getenv("GRAPH_CLIENT_SECRET", "").strip()
    if not value:
        raise GraphAuthError(
            "GRAPH_CLIENT_SECRET is required when GRAPH_AUTH_MODE=application."
        )
    return value


def shared_mailbox() -> str:
    value = os.getenv("GRAPH_MAILBOX", "").strip()
    if not value:
        raise GraphAuthError(
            "GRAPH_MAILBOX is required when GRAPH_AUTH_MODE=application."
        )
    return value


def authority() -> str:
    custom = os.getenv("GRAPH_AUTHORITY", "").strip()
    if custom:
        return custom
    if auth_mode() == "personal":
        return PERSONAL_AUTHORITY
    if auth_mode() == "device":
        return f"https://login.microsoftonline.com/{tenant_id()}"
    return f"https://login.microsoftonline.com/{tenant_id()}"


def is_configured() -> bool:
    """Return True when settings exist for the active auth mode."""
    if auth_mode() == "imap":
        from imap_client import is_configured as imap_configured

        return imap_configured()
    try:
        client_id()
        if auth_mode() == "application":
            client_secret()
            shared_mailbox()
        elif auth_mode() == "device":
            tenant_id()
        return True
    except GraphAuthError:
        return False


def mailbox_base_path() -> str:
    if auth_mode() == "application":
        return f"{GRAPH_ROOT}/users/{shared_mailbox()}"
    return f"{GRAPH_ROOT}/me"


def mailbox_label() -> str:
    if auth_mode() == "application":
        return shared_mailbox()
    return os.getenv("GRAPH_MAILBOX", "").strip() or "me"


def inbox_messages_url(*, top: int = 10) -> str:
    select = (
        "id,subject,from,receivedDateTime,bodyPreview,body,hasAttachments,"
        "toRecipients,ccRecipients"
    )
    return (
        f"{mailbox_base_path()}/mailFolders/inbox/messages"
        f"?$top={top}&$select={select}"
    )


def message_attachments_url(message_id: str) -> str:
    return f"{mailbox_base_path()}/messages/{message_id}/attachments"


def message_attachment_url(message_id: str, attachment_id: str) -> str:
    return f"{message_attachments_url(message_id)}/{attachment_id}"


def _acquire_application_token() -> str:
    app = ConfidentialClientApplication(
        client_id=client_id(),
        client_credential=client_secret(),
        authority=f"https://login.microsoftonline.com/{tenant_id()}",
    )
    result = app.acquire_token_for_client(scopes=GRAPH_SCOPE_DEFAULT)
    if not result or "access_token" not in result:
        error = (result or {}).get("error_description") or (result or {}).get("error")
        raise GraphAuthError(f"Application token request failed: {error}")
    return result["access_token"]


def _acquire_device_token() -> str:
    app = PublicClientApplication(client_id=client_id(), authority=authority())
    flow = app.initiate_device_flow(scopes=GRAPH_SCOPE_DELEGATED)
    if "message" not in flow:
        raise GraphAuthError(f"Device flow init failed: {flow}")

    logger.warning(flow["message"])

    while True:
        result = app.acquire_token_by_device_flow(flow)
        if result and "access_token" in result:
            return result["access_token"]
        if result.get("error") == "authorization_pending":
            time.sleep(flow.get("interval", 5))
            continue
        raise GraphAuthError(f"Device flow failed: {result}")


def acquire_token() -> str:
    if auth_mode() == "application":
        return _acquire_application_token()
    return _acquire_device_token()


def authorization_headers(token: str | None = None) -> dict[str, str]:
    access_token = token or acquire_token()
    return {"Authorization": f"Bearer {access_token}"}


def verify_mailbox_access(token: str | None = None) -> dict[str, Any]:
    headers = authorization_headers(token)
    url = inbox_messages_url(top=1)
    response = requests.get(url, headers=headers, timeout=30)

    payload: dict[str, Any] = {
        "auth_mode": auth_mode(),
        "mailbox": mailbox_label(),
        "graph_status": response.status_code,
        "ok": response.status_code == 200,
    }

    if response.status_code == 200:
        data = response.json()
        payload["sample_message_count"] = len(data.get("value", []))
    else:
        payload["error"] = response.text[:500]

    return payload
