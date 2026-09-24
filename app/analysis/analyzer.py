"""Combine expiration, issue checks and risk into one deterministic result."""
from datetime import datetime, timezone

from app.analysis.checks import run_checks
from app.analysis.risk import calculate_risk
from app.analysis.status import days_remaining, expiration_status
from app.config import DEFAULTS


def analyze(data: dict, endpoint: dict, config: dict | None = None,
            now: datetime | None = None) -> dict:
    """Analyze copied observation data, suitable for scans and later recalculation."""
    config = dict(config or DEFAULTS, now=now or datetime.now(timezone.utc))
    result = dict(data)
    result["days_left"] = days_remaining(data["not_after"], config["now"]) if data.get("not_after") and data.get("reachable") else None
    result["status"] = expiration_status(result["days_left"], config)
    result["issues"] = run_checks(result, endpoint, config)
    result.update(calculate_risk(result, endpoint, config))
    points = {reason["code"]: reason["points"] for reason in result["reasons"]}
    for issue in result["issues"]:
        issue["points"] = points.get(issue["code"], 0)
    return result
