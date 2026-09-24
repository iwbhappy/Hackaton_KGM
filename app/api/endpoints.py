"""Endpoint observations and lifecycle."""
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.api.scans import actor
from app.audit import audit_event
from app.db import SessionLocal
from app.models import Endpoint, Result
from app.repository import model_dict, result_dict
from app.scanner import SCAN_LOCK

router = APIRouter(prefix="/api/endpoints")


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
