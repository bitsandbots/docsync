"""Webhook and TextBelt SMS failure notifications."""

import json
import logging
import os
import urllib.parse
import urllib.request
from typing import Optional

log = logging.getLogger(__name__)

TEXTBELT_URL = "https://textbelt.com/text"


def _load_env() -> None:
    """Load .env from the repo root if present (no external dependencies)."""
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    env_path = os.path.normpath(env_path)
    if not os.path.isfile(env_path):
        return
    with open(env_path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())


_load_env()


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


def send_sms(message: str) -> Optional[str]:
    """Send an SMS via TextBelt. Returns error string or None on success."""
    key = os.environ.get("TEXTBELT_KEY", "")
    phone = os.environ.get("TEXTBELT_PHONE", "")
    if not key or not phone:
        return "TEXTBELT_KEY or TEXTBELT_PHONE not set"
    data = urllib.parse.urlencode({"phone": phone, "message": message, "key": key}).encode()
    req = urllib.request.Request(
        TEXTBELT_URL, data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode())
            if not body.get("success"):
                return body.get("error") or "TextBelt returned success=false"
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
    message = f"[DocSync] Backup FAILED — {source_name}: {error}"
    if url:
        payload = {"event": "backup_failure", "source": source_name, "error": error}
        err = send_webhook(url, payload)
        if err:
            log.warning("Webhook notification failed: %s", err)
    err = send_sms(message)
    if err:
        log.warning("SMS notification failed: %s", err)
    else:
        log.info("Sent SMS failure notification for '%s'", source_name)


def notify_success(config: dict, source_name: str, meta: dict) -> None:
    """Send success notification if configured."""
    notif = config.get("backup", {}).get("notifications", {})
    if not notif.get("on_success"):
        return
    url = notif.get("webhook_url", "")
    if not url:
        return
    message = f"[DocSync] Backup OK — {source_name}: {meta.get('file_count', 0)} files"
    if url:
        payload = {
            "event": "backup_success",
            "source": source_name,
            "snapshot": meta.get("timestamp"),
            "files": meta.get("file_count", 0),
        }
        send_webhook(url, payload)
    send_sms(message)
