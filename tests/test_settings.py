from cryptography import x509
from cryptography.hazmat.primitives import serialization
from pydantic import SecretStr

from app.config import settings
from tests.test_endpoints import add_result


def test_thresholds_recalculate_without_scan_and_validate(client):
    endpoint_id=add_result(owner="ИТ",days=45)
    before=client.get(f"/api/endpoints/{endpoint_id}").json()["latest"]
    assert before["status"] == "INFO"
    assert client.put("/api/settings",json={"threshold_info":40}).status_code == 200
    after=client.get(f"/api/endpoints/{endpoint_id}").json()["latest"]
    assert after["status"] == "OK" and after["scanned_at"] == before["scanned_at"]
    assert client.put("/api/settings",json={"threshold_warning":50}).status_code == 422
    assert client.put("/api/settings",json={"threshold_info":60,"threshold_warning":50}).status_code == 200
    assert client.get(f"/api/endpoints/{endpoint_id}").json()["latest"]["status"] == "WARNING"
    for payload in [{"concurrency":0},{"connect_timeout":-1},{"notification_thresholds":[]},{"smtp_password":"secret"},{"threshold_info":None}]:
        assert client.put("/api/settings",json=payload).status_code == 422
    assert len(client.get("/api/audit?action=settings_changed").json()) == 2


def test_root_ca_pem_der_reject_leaf_and_delete(client,lab_material):
    root=(lab_material[0]/"lab-root-ca.crt").read_bytes()
    cert=x509.load_pem_x509_certificate(root)
    for filename,data in [("root.pem",root),("root.cer",cert.public_bytes(serialization.Encoding.DER))]:
        response=client.post("/api/trusted-ca",files={"file":(filename,data)})
        assert response.status_code == 201,response.text
    rows=client.get("/api/trusted-ca").json()
    assert len(rows)==1 and rows[0]["cn"] == "Lab Root CA"
    assert (settings.trusted_ca_dir/rows[0]["name"]).read_bytes().startswith(b"-----BEGIN CERTIFICATE-----")
    assert client.post("/api/trusted-ca",files={"file":("leaf.pem",(lab_material[0]/"valid.crt").read_bytes())}).status_code == 422
    assert client.post("/api/trusted-ca",files={"file":("key.pem",(lab_material[0]/"valid.key").read_bytes())}).status_code == 422
    assert client.delete("/api/trusted-ca/..%5Cescape.pem").status_code == 422
    assert client.delete("/api/trusted-ca/"+rows[0]["name"]).status_code == 200
    assert client.get("/api/trusted-ca").json() == []
    assert client.get("/api/audit?action=trusted_ca_deleted").json()


def test_secrets_are_masked_and_pages_work(client,monkeypatch):
    monkeypatch.setattr(settings,"telegram_bot_token",SecretStr("1234567890:secret-token"))
    response=client.get("/api/notifications")
    assert "secret-token" not in response.text and "****" in response.text
    assert "telegram_bot_token" not in client.get("/api/settings").text
    assert client.get("/settings").status_code == client.get("/audit").status_code == 200
