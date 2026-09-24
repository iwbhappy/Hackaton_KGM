"""Explicit notification actions and delivery status."""
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.api.scans import actor
from app.audit import audit_event
from app.db import SessionLocal
from app.models import AuditLog
from app.notifiers.base import delivery_error
from app.notifiers.channels import channel_status, get_notifiers
from app.notifiers.dispatcher import dispatch
from app.repository import model_dict

router = APIRouter(prefix="/api/notifications")


@router.get("")
def status() -> dict:
    """Return masked channel setup and recent delivery failures."""
    with SessionLocal() as session:
        failures = list(session.scalars(select(AuditLog).where(AuditLog.action == "notification_failed").order_by(AuditLog.id.desc()).limit(10)))
    return {"channels": channel_status(), "failures": [model_dict(row) for row in failures]}


@router.post("/send-now")
def send_now(request: Request) -> dict:
    """Send the current digest regardless of earlier successful deliveries."""
    return dispatch(force=True, actor=actor(request))


@router.post("/test/{channel}")
def test_channel(channel: str, request: Request) -> dict:
    """Test one configured channel, with an audited and sanitized result."""
    notifier = get_notifiers().get(channel)
    if notifier is None:
        raise HTTPException(422, "Канал не настроен")
    error = None
    try:
        notifier.send("Certificate Radar: проверка канала", "Тестовое уведомление. Канал работает.")
    except Exception as exc:
        error = delivery_error(exc)
    with SessionLocal.begin() as session:
        audit_event(session, actor(request), "notification_failed" if error else "notification_sent",
                    {"channel": channel, "test": True, "error": error})
    return {"status": "failed" if error else "sent", "error": error}
