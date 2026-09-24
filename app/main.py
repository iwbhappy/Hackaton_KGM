"""FastAPI application and HTML pages."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import ROOT
from app.db import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Certificate Radar", lifespan=lifespan)
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
