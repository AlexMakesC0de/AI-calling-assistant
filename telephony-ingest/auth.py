from flask import request

from config import WEBHOOK_SHARED_TOKEN


def require_auth() -> bool:
    if not WEBHOOK_SHARED_TOKEN:
        return True
    token = request.headers.get("X-Telephony-Token", "")
    return token == WEBHOOK_SHARED_TOKEN
