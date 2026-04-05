"""Webhook and ntfy/Gotify failure notifications."""

import json
import logging
import urllib.request
from typing import Optional

log = logging.getLogger(__name__)


def send_webhook(url: str, payload: dict) -> Optional[str]:
    """POST *payload* as JSON to *url*. Returns error string or None."""
    if not url:
        return None
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status >= 400:
                return f"webhook returned HTTP {resp.status}"
    except Exception as exc:
        return str(exc)
    return None


def notify_failure(config: dict, source_name: str, error: str) -> None:
    """Send failure notification if configured."""
    notif = config.get("backup", {}).get("notifications", {})
    if not notif.get("on_failure"):
        return
    url = notif.get("webhook_url", "")
    if not url:
        return
    payload = {
        "event": "backup_failure",
        "source": source_name,
        "error": error,
    }
    err = send_webhook(url, payload)
    if err:
        log.warning("Failed to send failure notification: %s", err)
    else:
        log.info("Sent failure notification for '%s'", source_name)


def notify_success(config: dict, source_name: str, meta: dict) -> None:
    """Send success notification if configured."""
    notif = config.get("backup", {}).get("notifications", {})
    if not notif.get("on_success"):
        return
    url = notif.get("webhook_url", "")
    if not url:
        return
    payload = {
        "event": "backup_success",
        "source": source_name,
        "snapshot": meta.get("timestamp"),
        "files": meta.get("file_count", 0),
    }
    send_webhook(url, payload)
