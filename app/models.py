"""SQLite persistence models. All timestamps are UTC."""
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Endpoint(Base):
    __tablename__ = "endpoints"
    __table_args__ = (UniqueConstraint("host", "port"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    host: Mapped[str] = mapped_column(String(253))
    port: Mapped[int] = mapped_column(default=443)
    service_name: Mapped[str | None]
    owner: Mapped[str | None]
    criticality: Mapped[str] = mapped_column(default="normal")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class Scan(Base):
    __tablename__ = "scans"
    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(default=utcnow)
    finished_at: Mapped[datetime | None]
    status: Mapped[str] = mapped_column(default="running")
    targets_total: Mapped[int] = mapped_column(default=0)
    targets_ok: Mapped[int] = mapped_column(default=0)
    targets_failed: Mapped[int] = mapped_column(default=0)
    initiated_by: Mapped[str] = mapped_column(default="system")


class Result(Base):
    __tablename__ = "results"
    id: Mapped[int] = mapped_column(primary_key=True)
    scan_id: Mapped[int] = mapped_column(ForeignKey("scans.id"), index=True)
    endpoint_id: Mapped[int] = mapped_column(ForeignKey("endpoints.id", ondelete="CASCADE"), index=True)
    resolved_ip: Mapped[str | None]
    reachable: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None]
    tls_version: Mapped[str | None]
    subject_cn: Mapped[str | None]
    san_dns: Mapped[list] = mapped_column(JSON, default=list)
    san_ip: Mapped[list] = mapped_column(JSON, default=list)
    issuer_cn: Mapped[str | None]
    issuer_o: Mapped[str | None]
    serial: Mapped[str | None]
    thumbprint_sha1: Mapped[str | None]
    fingerprint_sha256: Mapped[str | None]
    not_before: Mapped[datetime | None] = mapped_column(DateTime)
    not_after: Mapped[datetime | None] = mapped_column(DateTime)
    days_left: Mapped[int | None]
    key_type: Mapped[str | None]
    key_size: Mapped[int | None]
    signature_algorithm: Mapped[str | None]
    has_aia: Mapped[bool] = mapped_column(default=False)
    chain_status: Mapped[str] = mapped_column(default="not_checked")
    chain_message: Mapped[str | None]
    hostname_match: Mapped[str] = mapped_column(default="not_checked")
    self_signed: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(default="ERROR")
    risk_score: Mapped[int | None]
    risk_level: Mapped[str | None]
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    issues: Mapped[list] = mapped_column(JSON, default=list)
    scanned_at: Mapped[datetime] = mapped_column(default=utcnow)


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[object] = mapped_column(JSON)


class NotificationSent(Base):
    __tablename__ = "notifications_sent"
    __table_args__ = (UniqueConstraint("thumbprint_sha1", "threshold_days", "channel"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    endpoint_id: Mapped[int] = mapped_column(ForeignKey("endpoints.id", ondelete="CASCADE"))
    thumbprint_sha1: Mapped[str]
    threshold_days: Mapped[int]
    channel: Mapped[str]
    sent_at: Mapped[datetime] = mapped_column(default=utcnow)
    success: Mapped[bool] = mapped_column(default=False)
    error: Mapped[str | None]


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(default=utcnow)
    actor: Mapped[str]
    action: Mapped[str] = mapped_column(index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
