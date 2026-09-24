"""Downloadable reports with audit events."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

from app.api.scans import actor
from app.audit import audit_event
from app.db import SessionLocal
from app.exporters.csv_export import export_csv
from app.exporters.html_report import export_html
from app.exporters.xlsx_export import export_xlsx
from app.repository import latest_results

router = APIRouter()


def dataset(request: Request, format: str) -> list[dict]:
    """Snapshot the latest results and audit the requested export."""
    with SessionLocal.begin() as session:
        rows = latest_results(session)
        audit_event(session, actor(request), "export_downloaded", {"format": format, "services": len(rows)})
    return rows


@router.get("/api/export/csv")
def csv_download(request: Request):
    """Download the UTF-8 BOM report."""
    return Response(export_csv(dataset(request, "csv")), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="certificate-radar.csv"'})


@router.get("/api/export/xlsx")
def xlsx_download(request: Request):
    """Download the styled three-sheet workbook."""
    return Response(export_xlsx(dataset(request, "xlsx")), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": 'attachment; filename="certificate-radar.xlsx"'})


@router.get("/report", response_class=HTMLResponse)
def report(request: Request):
    """Display a self-contained printable HTML report."""
    return export_html(dataset(request, "html"))
