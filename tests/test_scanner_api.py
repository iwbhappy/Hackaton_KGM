import socket
from time import monotonic

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import AuditLog


def route_lab(monkeypatch, lab_server, lab_material):
    original = socket.getaddrinfo

    def resolve(host, port, *args, **kwargs):
        if str(host).endswith(".lab.local"):
            host = "127.0.0.2" if host == "dead.lab.local" else "127.0.0.1"
            port = lab_server.server_address[1]
        elif host in {"127.0.0.1", "127.0.0.2"} and port == 443:
            port = lab_server.server_address[1]
        return original(host, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    monkeypatch.setattr(type(settings), "trusted_ca_dir", property(lambda self: lab_material[1]))


def test_scan_api_against_real_lab(client, lab_server, lab_material, monkeypatch):
    from app.config import ROOT
    route_lab(monkeypatch, lab_server, lab_material)
    text = (ROOT / "lab/targets.txt").read_text(encoding="utf-8")
    start = monotonic()
    response = client.post("/api/scans", json={"text": text})
    assert response.status_code == 202, response.text
    scan_id = response.json()["scan_id"]
    progress = client.get(f"/api/scans/{scan_id}").json()
    assert progress == {"scan_id": scan_id, "done": 15, "total": 15, "status": "done"}
    assert monotonic() - start < 15
    rows = client.get("/api/results").json()
    assert len(rows) == 15
    by_host = {r["host"]: r for r in rows}
    for name, status in [("valid", "OK"), ("info", "INFO"), ("warn", "WARNING"), ("soon", "CRITICAL"), ("expired", "EXPIRED"), ("dead", "ERROR")]:
        assert by_host[name + ".lab.local"]["status"] == status
    csv = (ROOT / "lab/targets.csv").read_bytes()
    assert client.post("/api/scans", files={"file": ("targets.csv", csv)}).status_code == 202
    rows = client.get("/api/results").json()
    vpn = next(r for r in rows if r["host"] == "vpn.lab.local")
    assert vpn["risk_score"] == 91
    assert len(rows) == 15  # Only the newest observation per service is returned.
    assert len(client.get(f"/api/endpoints/{vpn['endpoint_id']}").json()["history"]) == 2
    summary = client.get("/api/summary").json()
    assert summary["services"] == 15
    assert summary["statuses"]["ERROR"] == 2
    with SessionLocal() as session:
        actions = list(session.scalars(select(AuditLog.action)))
    assert actions.count("scan_started") == actions.count("scan_finished") == 2
    assert "scan_finished" in (settings.log_dir / "audit.log").read_text(encoding="utf-8")


def test_input_validation(client):
    assert client.post("/api/scans", json={"text": ""}).status_code == 422
    response = client.post("/api/targets/parse", json={"text": "10.0.0.0/30\nbad host"})
    assert len(response.json()["targets"]) == 2
    assert response.json()["errors"][0]["line"] == 2
    assert client.post("/api/scans", json={"text": "bad host"}).status_code == 422
    assert client.post("/api/scans", files={"file": ("big.txt", b"x" * (1024 * 1024 + 1))}).status_code == 413
    assert client.post("/api/scans", files={"file": ("bad.txt", b"\xff")}).status_code == 422
    assert client.get("/api/endpoints/9999").status_code == 404
