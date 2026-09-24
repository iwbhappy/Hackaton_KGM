"""One summary per channel and scan, deduplicated by certificate and threshold."""
from threading import Lock
from sqlalchemy import select

from app.audit import audit_event
from app.config import settings
from app.db import SessionLocal, get_settings
from app.models import NotificationSent, utcnow
from app.notifiers.base import delivery_error
from app.notifiers.channels import get_notifiers
from app.repository import latest_results

DISPATCH_LOCK = Lock()


def threshold_for(days: int | None, thresholds: list[int]) -> int | None:
    """Find the smallest reached threshold, treating expired certificates as zero."""
    if days is None:
        return None
    if days < 0:
        return 0
    return min((threshold for threshold in thresholds if days <= threshold), default=None)


def notification_text(rows: list[dict]) -> tuple[str, str]:
    """Create one bounded digest, referring to the dashboard for long inventories."""
    subject = f"Certificate Radar: {len(rows)} сервисов требуют внимания"
    lines = []
    for index, row in enumerate(rows):
        days = row["days_left"]
        expiry = f"ИСТЁК {-days} дн. назад" if days < 0 else f"истекает через {days} дн."
        line = (f"• {row['host']} — {expiry} ({str(row['not_after'])[:10]}), "
                f"риск {row['risk_score']}/100 {row['risk_level']}, владелец: {row['owner'] or 'не назначен'}")
        if sum(map(len, lines)) + len(line) > 2800:
            lines.append(f"…ещё {len(rows) - index} сервисов. Полный список в Dashboard.")
            break
        lines.append(line)
    lines.append("Открыть: " + settings.public_url)
    return subject, "\n".join(lines)


def record_delivery(rows: list[dict], channel: str, thresholds: list[int], success: bool,
                    error: str | None, actor: str) -> None:
    """Upsert one deduplication key; failed deliveries remain eligible for retry."""
    with SessionLocal.begin() as session:
        for row in rows:
            threshold = threshold_for(row["days_left"], thresholds)
            sent = session.scalar(select(NotificationSent).where(NotificationSent.thumbprint_sha1 == row["thumbprint_sha1"],
                    NotificationSent.threshold_days == threshold, NotificationSent.channel == channel))
            if sent is None:
                sent = NotificationSent(endpoint_id=row["endpoint_id"], thumbprint_sha1=row["thumbprint_sha1"],
                                        threshold_days=threshold, channel=channel)
                session.add(sent)
            # A failed forced resend must not erase an earlier successful delivery.
            if success or not sent.success:
                sent.success, sent.error, sent.sent_at = success, error, utcnow()
            session.flush()
        audit_event(session, actor, "notification_sent" if success else "notification_failed",
                    {"channel": channel, "count": len(rows), "error": error})


def dispatch(rows: list[dict] | None = None, force: bool = False,
             channels: dict | None = None, actor: str = "system") -> dict:
    """Send only new threshold crossings, or bypass deduplication on explicit request."""
    channels = get_notifiers() if channels is None else channels
    outcomes = {}
    with DISPATCH_LOCK:
        with SessionLocal() as session:
            rows = latest_results(session) if rows is None else rows
            thresholds = get_settings(session)["notification_thresholds"]
            sent = {(r.thumbprint_sha1, r.threshold_days, r.channel) for r in session.scalars(select(NotificationSent).where(NotificationSent.success.is_(True)))}
        candidates = sorted([r for r in rows if r.get("thumbprint_sha1") and r.get("reachable")
                             and threshold_for(r["days_left"], thresholds) is not None], key=lambda r: r["days_left"])
        for name, notifier in channels.items():
            pending = [r for r in candidates if force or (r["thumbprint_sha1"], threshold_for(r["days_left"], thresholds), name) not in sent]
            if not pending:
                outcomes[name] = {"status": "skipped", "count": 0}
                continue
            error = None
            try:
                notifier.send(*notification_text(pending))
            except Exception as exc:
                error = delivery_error(exc)
            record_delivery(pending, name, thresholds, error is None, error, actor)
            outcomes[name] = {"status": "failed" if error else "sent", "count": len(pending), "error": error}
    return {"channels": outcomes, "configured": bool(channels)}
