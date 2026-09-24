from unittest.mock import Mock
import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import NotificationSent, Result
from app.notifiers.dispatcher import dispatch, threshold_for
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
