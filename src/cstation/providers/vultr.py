from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from cstation.providers.base import VPS, VPSProvider, VPSStatus
from cstation.providers.errors import ProviderAuthError, ProviderError, ProviderNotFoundError, ProviderRateLimitError


def _status_from_vultr(value: str) -> VPSStatus:
    normalized = (value or "").strip().lower()
    if normalized in ("active", "running"):
        return VPSStatus.RUNNING
    if normalized in ("stopped", "halted", "suspended"):
        return VPSStatus.STOPPED
    if normalized in ("pending", "installing", "provisioning"):
        return VPSStatus.STARTING
    return VPSStatus.UNKNOWN


@dataclass
class VultrProvider(VPSProvider):
    token: str
    http: Any
    base_url: str = "https://api.vultr.com/v2"
    provider_name: str = "vultr"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def _handle_error(self, status_code: int) -> None:
        if status_code in (401, 403):
            raise ProviderAuthError("Vultr authentication failed")
        if status_code == 429:
            raise ProviderRateLimitError("Vultr rate limit exceeded")
        raise ProviderError(f"Vultr API error: {status_code}")

    def list_vps(self) -> list[VPS]:
        resp = self.http.get(f"{self.base_url}/instances", headers=self._headers())
        if resp.status_code != 200:
            self._handle_error(resp.status_code)

        data = resp.json() or {}
        out: list[VPS] = []
        for inst in data.get("instances", []) or []:
            out.append(
                VPS(
                    provider=self.provider_name,
                    id=str(inst.get("id")),
                    name=str(inst.get("label") or inst.get("hostname") or inst.get("id")),
                    region=str(inst.get("region")) if inst.get("region") is not None else None,
                    status=_status_from_vultr(str(inst.get("status", ""))),
                    ipv4=inst.get("main_ip"),
                    ipv6=inst.get("v6_main_ip"),
                )
            )
        return out

    def get_vps(self, *, id: Optional[str] = None, name: Optional[str] = None) -> VPS:
        if id:
            resp = self.http.get(f"{self.base_url}/instances/{id}", headers=self._headers())
            if resp.status_code == 404:
                raise ProviderNotFoundError("VPS not found")
            if resp.status_code != 200:
                self._handle_error(resp.status_code)

            inst = (resp.json() or {}).get("instance") or {}
            vcpu = inst.get("vcpu_count") if isinstance(inst, dict) else None
            memory_mb = inst.get("ram") if isinstance(inst, dict) else None
            disk_gb = inst.get("disk") if isinstance(inst, dict) else None
            bandwidth_gb = inst.get("allowed_bandwidth") if isinstance(inst, dict) else None
            plan = inst.get("plan") if isinstance(inst, dict) else None

            return VPS(
                provider=self.provider_name,
                id=str(inst.get("id")),
                name=str(inst.get("label") or inst.get("hostname") or inst.get("id")),
                region=str(inst.get("region")) if inst.get("region") is not None else None,
                status=_status_from_vultr(str(inst.get("status", ""))),
                ipv4=inst.get("main_ip"),
                ipv6=inst.get("v6_main_ip"),
                vcpu=int(vcpu) if isinstance(vcpu, int) and not isinstance(vcpu, bool) else None,
                memory_mb=int(memory_mb) if isinstance(memory_mb, int) and not isinstance(memory_mb, bool) else None,
                disk_gb=int(disk_gb) if isinstance(disk_gb, int) and not isinstance(disk_gb, bool) else None,
                bandwidth_gb=int(bandwidth_gb)
                if isinstance(bandwidth_gb, int) and not isinstance(bandwidth_gb, bool)
                else None,
                plan=str(plan) if isinstance(plan, str) and plan.strip() else None,
            )

        if name:
            for v in self.list_vps():
                if v.name == name:
                    return v
            raise ProviderNotFoundError("VPS not found")

        raise ProviderNotFoundError("VPS not found")

    def create_vps(
        self,
        *,
        name: str,
        region: str,
        server_type: str,
        image: str,
        ssh_keys: list[str],
    ) -> VPS:
        raise ProviderError("Vultr create is not supported in this CLI yet")

    def delete_vps(self, *, id: Optional[str] = None, name: Optional[str] = None) -> None:
        v = self.get_vps(id=id, name=name)
        resp = self.http.delete(f"{self.base_url}/instances/{v.id}", headers=self._headers())
        if resp.status_code not in (200, 204):
            self._handle_error(resp.status_code)
