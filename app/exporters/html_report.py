"""Standalone, escaped, printable HTML report without external assets."""
from datetime import datetime, timezone
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import ROOT
from app.exporters.common import COLUMNS, STATUS_LABELS, display_value
from app.repository import summarize


def export_html(rows: list[dict]) -> str:
    """Render a self-contained report with KPIs, risk reasons and remediation."""
    env = Environment(loader=FileSystemLoader(ROOT / "app/templates"), autoescape=select_autoescape(["html"]))
    return env.get_template("report.html").render(
        rows=rows, summary=summarize(rows), columns=COLUMNS[:14], display=display_value,
        status_labels=STATUS_LABELS, generated_at=datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC"))
