"""Shared result queries used by API, reports and notification dispatch."""
from datetime import datetime
from sqlalchemy import func, select

from app.analysis.status import as_utc
from app.models import Endpoint, Result


def model_dict(row) -> dict:
    """Serialize mapped columns with explicit UTC timestamps."""
    data = {column.name: getattr(row, column.name) for column in row.__table__.columns}
    return {key: as_utc(value).isoformat() if isinstance(value, datetime) else value for key, value in data.items()}


def latest_pairs(session) -> list[tuple]:
    """Return the newest scan result for each endpoint, including partial scans."""
    latest = select(Result.endpoint_id, func.max(Result.scan_id).label("scan_id")).group_by(Result.endpoint_id).subquery()
    query = (select(Result, Endpoint).join(Endpoint, Endpoint.id == Result.endpoint_id)
             .join(latest, (Result.endpoint_id == latest.c.endpoint_id) & (Result.scan_id == latest.c.scan_id)))
    return list(session.execute(query))


def result_dict(result: Result, endpoint: Endpoint) -> dict:
    """Flatten a result with current service metadata for display."""
    return dict(model_dict(result), host=endpoint.host, port=endpoint.port,
                service_name=endpoint.service_name or endpoint.host, owner=endpoint.owner,
                criticality=endpoint.criticality)


def latest_results(session) -> list[dict]:
    """Return the dashboard/report dataset, ordered by risk then remaining days."""
    rows = [result_dict(result, endpoint) for result, endpoint in latest_pairs(session)]
    return sorted(rows, key=lambda r: (-(r["risk_score"] if r["risk_score"] is not None else -1),
                                       r["days_left"] if r["days_left"] is not None else 999999))


def summarize(rows: list[dict]) -> dict:
    """Build dashboard KPIs, expiry buckets and the ten highest risk services."""
    statuses = {key: sum(row["status"] == key for row in rows)
                for key in ["OK", "INFO", "WARNING", "CRITICAL", "EXPIRED", "ERROR"]}
    issues = {code: sum(any(i["code"] == code for i in row["issues"]) for row in rows)
              for code in ["CHAIN_UNTRUSTED", "SELF_SIGNED", "HOSTNAME_MISMATCH", "NO_OWNER"]}
    issues["CHAIN"] = sum(row["chain_status"] not in {"valid", "valid_but_expired", "not_yet_valid", "not_checked"} for row in rows)
    scores = [row["risk_score"] for row in rows if row["risk_score"] is not None]
    buckets = [{"label": f"{start}–{end}", "count": sum(row["days_left"] is not None and start <= row["days_left"] <= end for row in rows)}
               for start, end in [(0, 7), (8, 14), (15, 30), (31, 60), (61, 90)]]
    return {"services": len(rows), "certificates": len({row["thumbprint_sha1"] for row in rows if row["thumbprint_sha1"]}),
            "statuses": statuses, "issues": issues, "health": round(100 - sum(scores) / len(scores)) if scores else None,
            "expiry_buckets": buckets, "top_risks": [row for row in rows if (row["risk_score"] or 0) > 0][:10]}
