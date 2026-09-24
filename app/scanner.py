"""Bounded parallel TLS collection with serialized database writes."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import logging

from sqlalchemy import select

from app.analysis.analyzer import analyze
from app.audit import audit_event
from app.collectors.tls_collector import TLSCollector, result_attributes
from app.db import SessionLocal, get_settings
from app.models import Endpoint, Result, Scan, utcnow
from app.parser import Target

SCAN_LOCK = Lock()
PROGRESS_LOCK = Lock()
PROGRESS: dict[int, dict] = {}


def create_scan(targets: list[Target], actor: str) -> int:
    """Persist a scan and its target metadata, preventing overlapping scans."""
    if not SCAN_LOCK.acquire(blocking=False):
        raise ValueError("Сканирование уже выполняется")
    try:
        with SessionLocal.begin() as session:
            scan = Scan(targets_total=len(targets), initiated_by=actor)
            session.add(scan)
            session.flush()
            for target in targets:
                endpoint = session.scalar(select(Endpoint).where(Endpoint.host == target.host, Endpoint.port == target.port))
                if endpoint is None:
                    endpoint = Endpoint(host=target.host, port=target.port, service_name=target.host)
                    session.add(endpoint)
                for key in ("service_name", "owner", "criticality"):
                    if getattr(target, key):
                        setattr(endpoint, key, getattr(target, key))
            audit_event(session, actor, "targets_uploaded", {"count": len(targets)})
            audit_event(session, actor, "scan_started", {"scan_id": scan.id, "targets": len(targets)})
        with PROGRESS_LOCK:
            if len(PROGRESS) >= 100:
                PROGRESS.pop(next(iter(PROGRESS)))
            PROGRESS[scan.id] = {"done": 0, "total": len(targets), "status": "running"}
        return scan.id
    except Exception:
        logging.getLogger("radar").exception("Не удалось создать сканирование")
        SCAN_LOCK.release()
        raise


def collect_one(target: Target, config: dict) -> dict:
    """Isolate a failed network operation or malformed leaf to one target."""
    try:
        raw = TLSCollector(timeout=config["connect_timeout"]).collect(target)
        return result_attributes(raw, target.host)
    except Exception:
        logging.getLogger("radar").exception("Не удалось разобрать TLS-ответ от %s:%s", target.host, target.port)
        return {"reachable": False, "error": "Не удалось разобрать ответ TLS-сервиса",
                "chain_status": "not_checked", "hostname_match": "not_checked"}


def save_result(scan_id: int, target: Target, data: dict, config: dict) -> None:
    """Analyze with current ownership and commit one observation plus counters."""
    with SessionLocal.begin() as session:
        endpoint = session.scalar(select(Endpoint).where(Endpoint.host == target.host, Endpoint.port == target.port))
        values = analyze(data, {key: getattr(endpoint, key) for key in ("host", "owner", "criticality")}, config)
        session.add(Result(scan_id=scan_id, endpoint_id=endpoint.id, **values))
        scan = session.get(Scan, scan_id)
        if data.get("reachable"):
            scan.targets_ok += 1
        else:
            scan.targets_failed += 1
        progress = {"done": scan.targets_ok + scan.targets_failed, "total": scan.targets_total, "status": "running"}
    with PROGRESS_LOCK:
        PROGRESS[scan_id] = progress


def run_scan(scan_id: int, targets: list[Target]) -> None:
    """Run collection in workers and persist progress even if a target fails."""
    status = "done"
    try:
        with SessionLocal() as session:
            config = get_settings(session)
        with ThreadPoolExecutor(max_workers=config["concurrency"]) as pool:
            pending = {pool.submit(collect_one, target, config): target for target in targets}
            for future in as_completed(pending):
                save_result(scan_id, pending[future], future.result(), config)
    except Exception:
        logging.getLogger("radar").exception("Сканирование %s завершилось с ошибкой", scan_id)
        status = "failed"
    finally:
        try:
            with SessionLocal.begin() as session:
                scan = session.get(Scan, scan_id)
                scan.status, scan.finished_at = status, utcnow()
                audit_event(session, "system", "scan_finished", {"scan_id": scan_id, "status": status,
                            "processed": scan.targets_ok + scan.targets_failed})
            with PROGRESS_LOCK:
                PROGRESS[scan_id]["status"] = status
        finally:
            SCAN_LOCK.release()
    if status == "done":
        try:
            from app.notifiers.dispatcher import dispatch
            from app.repository import result_dict
            with SessionLocal() as session:
                rows = [result_dict(result, endpoint) for result, endpoint in session.execute(
                    select(Result, Endpoint).join(Endpoint).where(Result.scan_id == scan_id))]
            dispatch(rows)
        except Exception:
            with SessionLocal.begin() as session:
                audit_event(session, "system", "notification_failed", {"error": "Не удалось подготовить уведомления", "scan_id": scan_id})
