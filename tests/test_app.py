from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.db import engine
from app.main import app


def test_health_and_schema():
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert "Certificate Radar" in client.get("/").text
    assert set(inspect(engine).get_table_names()) == {
        "endpoints", "scans", "results", "settings", "notifications_sent", "audit_log"
    }
