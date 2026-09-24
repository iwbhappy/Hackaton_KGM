"""Endpoint observations and lifecycle."""
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.api.scans import actor, read_input, parse_input
from app.audit import audit_event
from app.db import SessionLocal, get_settings
from app.models import Endpoint, Result
from app.repository import model_dict, result_dict, refresh_analysis
from app.scanner import SCAN_LOCK
from app.schemas import EndpointPatch

router = APIRouter(prefix="/api/endpoints")


@router.post("/import")
async def import_owners(request: Request) -> dict:
    """Import nonempty CSV service metadata, recalculating existing latest results."""
    parsed = parse_input(await read_input(request))
    if parsed.errors or not parsed.targets:
        raise HTTPException(422, {"message": "Исправьте ошибки CSV", "errors": parsed.errors})
    if not SCAN_LOCK.acquire(blocking=False):
        raise HTTPException(409, "Дождитесь завершения сканирования")
    try:
        with SessionLocal.begin() as session:
            config = get_settings(session)
            for target in parsed.targets:
                endpoint = session.scalar(select(Endpoint).where(Endpoint.host == target.host, Endpoint.port == target.port))
                if endpoint is None:
                    endpoint = Endpoint(host=target.host, port=target.port, service_name=target.host)
                    session.add(endpoint)
                for key in ("service_name", "owner", "criticality"):
                    if getattr(target, key):
                        setattr(endpoint, key, getattr(target, key))
                session.flush()
                latest = session.scalar(select(Result).where(Result.endpoint_id == endpoint.id).order_by(Result.scan_id.desc()).limit(1))
                if latest:
                    refresh_analysis(latest, endpoint, config)
                audit_event(session, actor(request), "endpoint_updated", {"endpoint_id": endpoint.id, "source": "csv"})
            audit_event(session, actor(request), "targets_uploaded", {"count": len(parsed.targets), "source": "csv"})
        return {"updated": len(parsed.targets)}
    finally:
        SCAN_LOCK.release()


@router.patch("/{endpoint_id}")
def update_endpoint(endpoint_id: int, payload: EndpointPatch, request: Request) -> dict:
    """Update ownership and immediately refresh risk on the latest observation."""
    changes = payload.model_dump(exclude_unset=True)
    if "criticality" in changes and changes["criticality"] is None:
        raise HTTPException(422, "Укажите критичность сервиса")
    if not SCAN_LOCK.acquire(blocking=False):
        raise HTTPException(409, "Дождитесь завершения сканирования")
    try:
        with SessionLocal.begin() as session:
            endpoint = session.get(Endpoint, endpoint_id)
            if endpoint is None:
                raise HTTPException(404, "Сервис не найден")
            for key, value in changes.items():
                setattr(endpoint, key, value)
            latest = session.scalar(select(Result).where(Result.endpoint_id == endpoint_id).order_by(Result.scan_id.desc()).limit(1))
            if latest:
                refresh_analysis(latest, endpoint, get_settings(session))
            audit_event(session, actor(request), "endpoint_updated", {"endpoint_id": endpoint_id, "changes": changes})
        return endpoint_details(endpoint_id)
    finally:
        SCAN_LOCK.release()


@router.get("/{endpoint_id}")
def endpoint_details(endpoint_id: int) -> dict:
    """Return service metadata and complete observation history."""
    with SessionLocal() as session:
        endpoint = session.get(Endpoint, endpoint_id)
        if endpoint is None:
            raise HTTPException(404, "Сервис не найден")
        rows = list(session.scalars(select(Result).where(Result.endpoint_id == endpoint_id).order_by(Result.scan_id.desc())))
        return {"endpoint": model_dict(endpoint), "latest": result_dict(rows[0], endpoint) if rows else None,
                "history": [model_dict(row) for row in rows]}


@router.delete("/{endpoint_id}")
def delete_endpoint(endpoint_id: int, request: Request) -> dict:
    """Delete a service and its results when no scan is using it."""
    if not SCAN_LOCK.acquire(blocking=False):
        raise HTTPException(409, "Дождитесь завершения сканирования")
    try:
        with SessionLocal.begin() as session:
            endpoint = session.get(Endpoint, endpoint_id)
            if endpoint is None:
                raise HTTPException(404, "Сервис не найден")
            audit_event(session, actor(request), "endpoint_deleted", {"endpoint_id": endpoint_id})
            session.delete(endpoint)
        return {"status": "ok"}
    finally:
        SCAN_LOCK.release()
