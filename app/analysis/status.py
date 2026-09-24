"""Expiration statuses are independent from trust and cryptographic issues."""
from datetime import datetime, timezone
from math import floor

from app.config import DEFAULTS


def as_utc(value: datetime | str) -> datetime:
    """Interpret SQLite naive timestamps as UTC and accept API ISO strings."""
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def days_remaining(not_after: datetime | str, now: datetime | None = None) -> int:
    """Count complete days using floor, including the first second after expiry."""
    return floor((as_utc(not_after) - as_utc(now or datetime.now(timezone.utc))).total_seconds() / 86400)


def validate_thresholds(config: dict) -> None:
    """Require decreasing non-negative status thresholds."""
    if not (config["threshold_info"] > config["threshold_warning"] > config["threshold_critical"] >= 0):
        raise ValueError("Пороги должны удовлетворять: info > warning > critical ≥ 0")


def expiration_status(days_left: int | None, config: dict | None = None) -> str:
    """Return only the certificate expiration status."""
    config = config or DEFAULTS
    validate_thresholds(config)
    if days_left is None:
        return "ERROR"
    if days_left < 0:
        return "EXPIRED"
    for key, status in [("threshold_critical", "CRITICAL"), ("threshold_warning", "WARNING"),
                        ("threshold_info", "INFO")]:
        if days_left <= config[key]:
            return status
    return "OK"
