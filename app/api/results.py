"""Latest results and dashboard aggregates."""
from fastapi import APIRouter
from app.db import SessionLocal
from app.repository import latest_results, summarize

router = APIRouter(prefix="/api")


@router.get("/results")
def results() -> list[dict]:
    """Return one latest result per service."""
    with SessionLocal() as session:
        return latest_results(session)


@router.get("/summary")
def summary() -> dict:
    """Return KPIs, chart data and top risk services."""
    return summarize(results())
