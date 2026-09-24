from datetime import datetime, timedelta, timezone
from sqlalchemy import select

from app.analysis.analyzer import analyze
from app.db import SessionLocal
from app.models import Endpoint, Result, Scan


def add_result(owner=None, criticality="normal", days=100):
    with SessionLocal.begin() as session:
        endpoint=Endpoint(host="test.local", owner=owner, criticality=criticality)
        scan=Scan(status="done")
        session.add_all([endpoint,scan]); session.flush()
        values=analyze({"reachable":True,"not_after":datetime.now(timezone.utc)+timedelta(days=days,hours=1),
                        "thumbprint_sha1":"A"*40,"chain_status":"valid","hostname_match":"match"},
                       {"owner":owner,"criticality":criticality})
        session.add(Result(endpoint_id=endpoint.id, scan_id=scan.id, **values))
        return endpoint.id


def test_owner_recalculates_risk_and_criticality(client):
    endpoint_id=add_result(criticality="critical",days=100)
    before=client.get(f"/api/endpoints/{endpoint_id}").json()["latest"]
    response=client.patch(f"/api/endpoints/{endpoint_id}",json={"owner":"Иванов И."})
    assert response.status_code == 200
    after=response.json()["latest"]
    assert before["risk_score"] - after["risk_score"] == 13
    assert "NO_OWNER" not in {i["code"] for i in after["issues"]}
    assert after["scanned_at"] == before["scanned_at"]
    changed=client.patch(f"/api/endpoints/{endpoint_id}",json={"criticality":"low"}).json()
    assert changed["latest"]["risk_score"] == 0
    assert len(changed["history"]) == 1
    assert client.get(f"/endpoint/{endpoint_id}").status_code == 200
    assert client.patch(f"/api/endpoints/{endpoint_id}",json={"criticality":"invalid"}).status_code == 422


def test_criticality_changes_existing_risk(client):
    endpoint_id=add_result(owner="ИТ",criticality="critical",days=25)
    assert client.get(f"/api/endpoints/{endpoint_id}").json()["latest"]["risk_score"] == 46
    changed=client.patch(f"/api/endpoints/{endpoint_id}",json={"criticality":"low"}).json()
    assert changed["latest"]["risk_score"] == 30


def test_csv_metadata_updates_only_nonempty_and_deletes(client):
    endpoint_id=add_result(owner="Existing")
    response=client.post("/api/endpoints/import",json={"text":"target;owner;service_name\ntest.local;;Новый сервис"})
    assert response.status_code == 200
    data=client.get(f"/api/endpoints/{endpoint_id}").json()
    assert data["endpoint"]["owner"] == "Existing"
    assert data["endpoint"]["service_name"] == "Новый сервис"
    assert client.delete(f"/api/endpoints/{endpoint_id}").status_code == 200
    assert client.get(f"/api/endpoints/{endpoint_id}").status_code == 404
    with SessionLocal() as session:
        assert not list(session.scalars(select(Result)))
