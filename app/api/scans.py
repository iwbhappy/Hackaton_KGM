"""Target preview and background scan endpoints."""
import json
from dataclasses import asdict

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy import select

from app.db import SessionLocal, get_settings
from app.models import Endpoint, Scan
from app.parser import MAX_UPLOAD, Target, normalize_host, parse_targets
from app.repository import model_dict
from app.scanner import PROGRESS, PROGRESS_LOCK, create_scan, run_scan
from app.schemas import ScanInput

router = APIRouter(prefix="/api")


def actor(request: Request) -> str:
    """Identify a local action by its actual peer address."""
    return request.client.host if request.client else "system"


async def read_input(request: Request) -> ScanInput:
    """Read bounded JSON or a multipart UTF-8 file with a common schema."""
    if request.headers.get("content-type", "").startswith("multipart/form-data"):
        form = await request.form(max_files=1, max_fields=3, max_part_size=MAX_UPLOAD)
        upload = form.get("file")
        if upload is None or not hasattr(upload, "read"):
            raise HTTPException(422, "Загрузите файл .txt или .csv")
        filename = upload.filename or ""
        if not filename.lower().endswith((".txt", ".csv")):
            raise HTTPException(422, "Поддерживаются файлы .txt и .csv")
        data = await upload.read(MAX_UPLOAD + 1)
        await upload.close()
        if len(data) > MAX_UPLOAD:
            raise HTTPException(413, "Размер файла превышает 1 МБ")
        try:
            return ScanInput(text=data.decode("utf-8-sig"), filename=filename)
        except UnicodeError:
            raise HTTPException(422, "Файл должен быть в кодировке UTF-8") from None
    try:
        return ScanInput.model_validate(await request.json())
    except (ValueError, ValidationError):
        raise HTTPException(422, "Некорректный JSON: ожидается text или rescan_all") from None


def parse_input(payload: ScanInput):
    """Apply the persisted parser limits."""
    with SessionLocal() as session:
        config = get_settings(session)
    return parse_targets(payload.text, payload.filename, config["max_cidr_hosts"], config["max_targets"])


@router.post("/targets/parse")
async def preview(request: Request) -> dict:
    """Preview targets and per-line errors before scanning."""
    return parse_input(await read_input(request)).to_dict()


@router.post("/scans", status_code=202)
async def start_scan(request: Request, background: BackgroundTasks) -> dict:
    """Create a background scan after validating all requested targets."""
    payload = await read_input(request)
    if payload.rescan_all:
        with SessionLocal() as session:
            targets = [Target(row.host, row.port, normalize_host(row.host)[1]) for row in session.scalars(select(Endpoint))]
            if len(targets) > get_settings(session)["max_targets"]:
                raise HTTPException(422, "Число сохранённых целей превышает лимит сканирования")
    else:
        parsed = parse_input(payload)
        if parsed.errors:
            raise HTTPException(422, {"message": "Исправьте ошибки списка целей", "errors": parsed.errors})
        targets = parsed.targets
    if not targets:
        raise HTTPException(422, "Нет целей для сканирования")
    try:
        scan_id = create_scan(targets, actor(request))
    except ValueError as error:
        raise HTTPException(409, str(error)) from None
    background.add_task(run_scan, scan_id, targets)
    return {"scan_id": scan_id}


@router.get("/scans")
def scans() -> list[dict]:
    """List recent scans."""
    with SessionLocal() as session:
        return [model_dict(row) for row in session.scalars(select(Scan).order_by(Scan.id.desc()).limit(100))]


@router.get("/scans/{scan_id}")
def scan_progress(scan_id: int) -> dict:
    """Return in-memory progress with a persistent fallback after restart."""
    with SessionLocal() as session:
        scan = session.get(Scan, scan_id)
        if scan is None:
            raise HTTPException(404, "Сканирование не найдено")
        progress = {"done": scan.targets_ok + scan.targets_failed, "total": scan.targets_total, "status": scan.status}
    with PROGRESS_LOCK:
        return dict(PROGRESS.get(scan_id, progress), scan_id=scan_id)
