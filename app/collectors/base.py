"""Collector interface shared by network observation plugins."""
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.parser import Target


@dataclass
class RawObservation:
    der: bytes | None = None
    reachable: bool = False
    resolved_ip: str | None = None
    tls_version: str | None = None
    error: str | None = None
    chain_status: str = "not_checked"
    chain_message: str | None = None


class BaseCollector(ABC):
    @abstractmethod
    def collect(self, target: Target) -> RawObservation:
        """Collect information without changing the remote service."""
