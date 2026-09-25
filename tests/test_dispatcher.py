from unittest.mock import Mock
import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import NotificationSent, Result
from app.notifiers.dispatcher import dispatch, notification_text, threshold_for
from tests.test_endpoints import add_result


@pytest.mark.parametrize("days,expected", [(80,None),(60,60),(31,60),(30,30),(14,14),(7,7),(5,7),(1,1),(0,1),(-1,0),(None,None)])
def test_thresholds(days,expected):
    assert threshold_for(days,[60,30,14,7,1]) == expected


def test_dedup_new_certificate_forced_retry(client):
    add_result(owner="ИТ",days=5)
    notifier=Mock()
    assert dispatch(channels={"telegram":notifier})["channels"]["telegram"]["status"] == "sent"
    assert dispatch(channels={"telegram":notifier})["channels"]["telegram"]["status"] == "skipped"
    assert notifier.send.call_count == 1
    dispatch(force=True,channels={"telegram":notifier})
    assert notifier.send.call_count == 2
    with SessionLocal.begin() as session:
        session.scalar(select(Result)).thumbprint_sha1="B"*40
    notifier.send.side_effect=RuntimeError("secret-token-must-not-leak")
    assert dispatch(channels={"telegram":notifier})["channels"]["telegram"]["status"] == "failed"
    notifier.send.side_effect=None
    assert dispatch(channels={"telegram":notifier})["channels"]["telegram"]["status"] == "sent"
    with SessionLocal() as session:
        rows=list(session.scalars(select(NotificationSent)))
        assert len(rows)==2 and all(row.success for row in rows)
        assert all("secret-token" not in (row.error or "") for row in rows)


def test_unconfigured_channels_are_explicit(client):
    assert client.post("/api/notifications/test/telegram").status_code == 422
    assert client.post("/api/notifications/send-now").json()["configured"] is False
    assert client.get("/api/notifications").json()["channels"]["telegram"]["configured"] is False


def test_latest_notification_error_clears_after_success(client, monkeypatch):
    notifier = Mock()
    monkeypatch.setattr("app.api.notifications.get_notifiers", lambda: {"telegram": notifier})
    assert client.get("/api/notifications").json()["last_error"] is None
    notifier.send.side_effect = RuntimeError("private delivery details")
    failed = client.post("/api/notifications/test/telegram").json()
    status = client.get("/api/notifications").json()
    assert failed["status"] == "failed"
    assert status["last_error"] == failed["error"]
    assert len(status["failures"]) == 1
    notifier.send.side_effect = None
    assert client.post("/api/notifications/test/telegram").json()["status"] == "sent"
    status = client.get("/api/notifications").json()
    assert status["last_error"] is None
    assert len(status["failures"]) == 1


@pytest.mark.parametrize("count,phrase", [
    (1, "сертификат требует"), (2, "сертификата требуют"), (5, "сертификатов требуют"),
    (11, "сертификатов требуют"), (21, "сертификат требует"),
])
def test_notification_wording(count, phrase):
    row = {"host": "vpn.lab.local", "days_left": 5, "not_after": "2026-09-30T12:00:00+00:00",
           "risk_score": 91, "risk_level": "Critical", "owner": "Иванов И.", "status": "CRITICAL"}
    subject, text = notification_text([row] * count)
    assert subject == f"🔴 Certificate Radar: {count} {phrase} внимания"
    assert text.splitlines()[0] == (
        "• vpn.lab.local — истекает через 5 дн. (30.09.2026), риск 91/100 Critical, владелец: Иванов И."
    )
    row.update(status="WARNING", days_left=25)
    assert notification_text([row])[0].startswith("🟡")
    row.update(status="EXPIRED", days_left=-5)
    subject, text = notification_text([row])
    assert subject.startswith("🔴")
    assert "ИСТЁК 5 дн. назад" in text
