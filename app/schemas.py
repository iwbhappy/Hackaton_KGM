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
