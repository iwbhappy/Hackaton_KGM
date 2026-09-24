"""Validated non-secret settings, public CA files and the audit journal."""
from fastapi import APIRouter, HTTPException, Query, Request, UploadFile, File
from sqlalchemy import select

from app.analysis.status import validate_thresholds
from app.api.scans import actor
from app.audit import audit_event
from app.config import settings
from app.db import SessionLocal, get_settings
from app.models import AuditLog, Setting
from app.parser import MAX_UPLOAD
from app.repository import latest_pairs, model_dict, refresh_analysis
from app.scanner import SCAN_LOCK
from app.schemas import SettingsPatch
from app.trusted_ca import ca_info, save_ca, delete_ca

router = APIRouter(prefix="/api")


@router.get("/settings")
def read_settings() -> dict:
    """Return application controls; secrets are never database settings."""
    with SessionLocal() as session:
        return get_settings(session)


@router.put("/settings")
def update_settings(payload: SettingsPatch, request: Request) -> dict:
    """Atomically validate settings and recalculate every latest result."""
    changes = payload.model_dump(exclude_unset=True)
    if any(value is None for value in changes.values()):
        raise HTTPException(422, "Настройки не могут быть пустыми")
    if not SCAN_LOCK.acquire(blocking=False):
        raise HTTPException(409, "Дождитесь завершения сканирования")
    try:
        with SessionLocal.begin() as session:
            config = dict(get_settings(session), **changes)
            try:
                validate_thresholds(config)
            except ValueError as error:
                raise HTTPException(422, str(error)) from None
            for key, value in changes.items():
                session.get(Setting, key).value = value
            for result, endpoint in latest_pairs(session):
                refresh_analysis(result, endpoint, config)
            audit_event(session, actor(request), "settings_changed", changes)
        return config
    finally:
        SCAN_LOCK.release()


@router.get("/trusted-ca")
def trusted_ca_list() -> list[dict]:
    """List additional trust roots and expiration dates."""
    return [ca_info(path) for path in sorted(settings.trusted_ca_dir.glob("*"))
            if path.suffix.lower() in {".pem", ".crt", ".cer"} and not path.is_symlink() and path.is_file()]


@router.post("/trusted-ca", status_code=201)
async def upload_ca(request: Request, file: UploadFile = File(...)) -> dict:
    """Validate, convert and store an uploaded public CA certificate."""
    if not (file.filename or "").lower().endswith((".pem", ".crt", ".cer")):
        raise HTTPException(422, "Поддерживаются сертификаты .pem, .crt и .cer")
    data = await file.read(MAX_UPLOAD + 1)
    await file.close()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "Размер файла превышает 1 МБ")
    if not SCAN_LOCK.acquire(blocking=False):
        raise HTTPException(409, "Дождитесь завершения сканирования")
    try:
        try:
            info = save_ca(data)
        except ValueError as error:
            raise HTTPException(422, str(error)) from None
        with SessionLocal.begin() as session:
            audit_event(session, actor(request), "trusted_ca_uploaded", info)
        return info
    finally:
        SCAN_LOCK.release()


@router.delete("/trusted-ca/{name}")
def remove_ca(name: str, request: Request) -> dict:
    """Delete an additional trust anchor and audit the action."""
    if not SCAN_LOCK.acquire(blocking=False):
        raise HTTPException(409, "Дождитесь завершения сканирования")
    try:
        try:
            delete_ca(name)
        except FileNotFoundError:
            raise HTTPException(404, "Сертификат не найден") from None
        except ValueError as error:
            raise HTTPException(422, str(error)) from None
        with SessionLocal.begin() as session:
            audit_event(session, actor(request), "trusted_ca_deleted", {"name": name})
        return {"status": "ok"}
    finally:
        SCAN_LOCK.release()


@router.get("/audit")
def audit(action: str | None = Query(default=None, max_length=80)) -> list[dict]:
    """Read the latest 500 audit entries, optionally filtered by action."""
    query = select(AuditLog).order_by(AuditLog.id.desc()).limit(500)
    if action:
        query = query.where(AuditLog.action == action)
    with SessionLocal() as session:
        return [model_dict(row) for row in session.scalars(query)]
