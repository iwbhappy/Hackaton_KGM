"""FastAPI application and HTML pages."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import ROOT
from app.db import init_db
from app.db import SessionLocal
from app.audit import audit_event
from app.api import scans, results, endpoints
from app.middleware import BodyLimitMiddleware
from app.models import Scan, utcnow
from sqlalchemy import select


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    with SessionLocal.begin() as session:
        for scan in session.scalars(select(Scan).where(Scan.status == "running")):
            scan.status, scan.finished_at = "failed", utcnow()
            audit_event(session, "system", "scan_finished", {"scan_id": scan.id, "status": "failed", "reason": "Приложение перезапущено"})
        audit_event(session, "system", "app_started")
    yield


app = FastAPI(title="Certificate Radar", lifespan=lifespan)
app.add_middleware(BodyLimitMiddleware)
for router in [scans.router, results.router, endpoints.router]:
    app.include_router(router)
app.mount("/static", StaticFiles(directory=ROOT / "app/static"), name="static")
templates = Jinja2Templates(directory=ROOT / "app/templates")


@app.get("/health")
def health() -> dict:
    """Check that the application is running."""
    return {"status": "ok"}


@app.get("/")
def dashboard(request: Request):
    """Render the application shell."""
    return templates.TemplateResponse(request=request, name="base.html")
