from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from cstation.providers.base import VPS, VPSProvider, VPSStatus
from cstation.providers.errors import ProviderAuthError, ProviderError, ProviderNotFoundError


def _status_from_hetzner(value: str) -> VPSStatus:
    try:
        return VPSStatus(value)
    except Exception:
        return VPSStatus.UNKNOWN


def _traffic_to_gb(value: object) -> Optional[int]:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        if value >= 1024**3:
            return int(round(value / (1024**3)))
        if value > 0:
            return value
        return None
    if isinstance(value, float):
        if value > 0:
            return int(round(value))
        return None
    return None


@dataclass
class HetznerProvider(VPSProvider):
    token: str
    http: Any
    base_url: str = "https://api.hetzner.cloud/v1"
    provider_name: str = "hetzner"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def _handle_error(self, status_code: int) -> None:
        if status_code in (401, 403):
            raise ProviderAuthError("Hetzner authentication failed")
        raise ProviderError(f"Hetzner API error: {status_code}")

    def list_vps(self) -> list[VPS]:
        resp = self.http.get(f"{self.base_url}/servers", headers=self._headers())
        if resp.status_code != 200:
            self._handle_error(resp.status_code)

        data = resp.json()
        out: list[VPS] = []
        for s in data.get("servers", []):
            public_net = s.get("public_net") or {}
            ipv4 = (public_net.get("ipv4") or {}).get("ip")
            ipv6 = (public_net.get("ipv6") or {}).get("ip")
            region = (((s.get("datacenter") or {}).get("location") or {}).get("name"))

            out.append(
                VPS(
                    provider=self.provider_name,
                    id=str(s.get("id")),
                    name=str(s.get("name")),
                    region=region,
                    status=_status_from_hetzner(str(s.get("status", ""))),
                    ipv4=ipv4,
                    ipv6=ipv6,
                )
            )
        return out

    def get_vps(self, *, id: Optional[str] = None, name: Optional[str] = None) -> VPS:
        if id:
            resp = self.http.get(f"{self.base_url}/servers/{id}", headers=self._headers())
            if resp.status_code == 404:
                raise ProviderNotFoundError("VPS not found")
            if resp.status_code != 200:
                self._handle_error(resp.status_code)

            s = (resp.json() or {}).get("server") or {}
            public_net = s.get("public_net") or {}
            ipv4 = (public_net.get("ipv4") or {}).get("ip")
            ipv6 = (public_net.get("ipv6") or {}).get("ip")
            region = (((s.get("datacenter") or {}).get("location") or {}).get("name"))

            server_type = s.get("server_type") or {}
            vcpu = server_type.get("cores") if isinstance(server_type, dict) else None
            memory_gb = server_type.get("memory") if isinstance(server_type, dict) else None
            disk_gb = server_type.get("disk") if isinstance(server_type, dict) else None
            included_traffic = server_type.get("included_traffic") if isinstance(server_type, dict) else None
            plan = server_type.get("name") if isinstance(server_type, dict) else None

            memory_mb = None
            if isinstance(memory_gb, (int, float)) and not isinstance(memory_gb, bool):
                memory_mb = int(round(float(memory_gb) * 1024))

            return VPS(
                provider=self.provider_name,
                id=str(s.get("id")),
                name=str(s.get("name")),
                region=region,
                status=_status_from_hetzner(str(s.get("status", ""))),
                ipv4=ipv4,
                ipv6=ipv6,
                vcpu=int(vcpu) if isinstance(vcpu, int) and not isinstance(vcpu, bool) else None,
                memory_mb=memory_mb,
                disk_gb=int(disk_gb) if isinstance(disk_gb, int) and not isinstance(disk_gb, bool) else None,
                bandwidth_gb=_traffic_to_gb(included_traffic),
                plan=str(plan) if isinstance(plan, str) and plan.strip() else None,
            )

        vps_list = self.list_vps()
        for v in vps_list:
            if name and v.name == name:
                return v
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
        payload = {
            "name": name,
            "location": region,
            "server_type": server_type,
            "image": image,
            "ssh_keys": ssh_keys,
        }
        resp = self.http.post(f"{self.base_url}/servers", headers=self._headers(), json=payload)
        if resp.status_code not in (200, 201):
            self._handle_error(resp.status_code)

        server = (resp.json() or {}).get("server") or {}
        return VPS(
            provider=self.provider_name,
            id=str(server.get("id")),
            name=str(server.get("name")),
            region=region,
            status=_status_from_hetzner(str(server.get("status", ""))),
        )

    def delete_vps(self, *, id: Optional[str] = None, name: Optional[str] = None) -> None:
        v = self.get_vps(id=id, name=name)
        resp = self.http.delete(f"{self.base_url}/servers/{v.id}", headers=self._headers())
        if resp.status_code not in (200, 204):
            self._handle_error(resp.status_code)
