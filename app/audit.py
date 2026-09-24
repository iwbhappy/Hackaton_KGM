"""Structured audit events, duplicated to SQLite and a local JSON-lines log."""
import json
from threading import Lock

from app.config import settings
from app.models import AuditLog, utcnow

FILE_LOCK = Lock()


def redact(value):
    """Remove configured credentials recursively before any persistence."""
    if isinstance(value, dict):
        return {key: "****" if any(word in key.lower() for word in ("password", "token", "webhook"))
                else redact(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        for secret in [settings.telegram_bot_token, settings.smtp_password, settings.teams_webhook_url]:
            raw = secret.get_secret_value()
            if raw:
                value = value.replace(raw, "****")
    return value


def audit_event(session, actor: str, action: str, details: dict | None = None) -> None:
    """Append a sanitized audit entry in the current database transaction."""
    timestamp, details = utcnow(), redact(details or {})
    session.add(AuditLog(ts=timestamp, actor=redact(actor), action=action, details=details))
    entry = {"ts": timestamp.isoformat(), "actor": redact(actor), "action": action, "details": details}
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    with FILE_LOCK, (settings.log_dir / "audit.log").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
