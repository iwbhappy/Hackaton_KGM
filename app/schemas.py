"""Validated JSON request schemas."""
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Literal


class ScanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = ""
    filename: str = ""
    rescan_all: bool = False


class EndpointPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    service_name: str | None = Field(default=None, max_length=253)
    owner: str | None = Field(default=None, max_length=253)
    criticality: Literal["low", "normal", "high", "critical"] | None = None

    @field_validator("service_name", "owner")
    @classmethod
    def strip_value(cls, value):
        """Normalize empty editable fields."""
        return value.strip() or None if value is not None else None


class SettingsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    threshold_info: int | None = Field(default=None, ge=1, le=3650)
    threshold_warning: int | None = Field(default=None, ge=1, le=3650)
    threshold_critical: int | None = Field(default=None, ge=0, le=3650)
    notification_thresholds: list[int] | None = None
    concurrency: int | None = Field(default=None, ge=1, le=128)
    connect_timeout: float | None = Field(default=None, ge=0.2, le=30)
    max_cidr_hosts: int | None = Field(default=None, ge=1, le=65536)
    max_targets: int | None = Field(default=None, ge=1, le=2048)

    @field_validator("notification_thresholds")
    @classmethod
    def valid_notification_thresholds(cls, value):
        """Require a nonempty bounded list of positive notification thresholds."""
        if value is not None and (not value or len(value) > 20 or any(not 1 <= x <= 3650 for x in value)):
            raise ValueError("Пороги уведомлений: от 1 до 3650 дней, не более 20 значений")
        return sorted(set(value), reverse=True) if value is not None else None
