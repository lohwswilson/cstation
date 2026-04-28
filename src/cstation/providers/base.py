from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Protocol


class VPSStatus(str, Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    STARTING = "starting"
    STOPPING = "stopping"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class VPS:
    provider: str
    id: str
    name: str
    region: Optional[str]
    status: VPSStatus
    ipv4: Optional[str] = None
    ipv6: Optional[str] = None
    vcpu: Optional[int] = None
    memory_mb: Optional[int] = None
    disk_gb: Optional[int] = None
    bandwidth_gb: Optional[int] = None
    plan: Optional[str] = None


class VPSProvider(Protocol):
    provider_name: str

    def list_vps(self) -> list[VPS]: ...

    def get_vps(self, *, id: Optional[str] = None, name: Optional[str] = None) -> VPS: ...

    def create_vps(
        self,
        *,
        name: str,
        region: str,
        server_type: str,
        image: str,
        ssh_keys: list[str],
    ) -> VPS: ...

    def delete_vps(self, *, id: Optional[str] = None, name: Optional[str] = None) -> None: ...
