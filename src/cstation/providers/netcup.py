from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from cstation.providers.base import VPS, VPSProvider, VPSStatus
from cstation.providers.errors import ProviderAuthError, ProviderError, ProviderNotFoundError


_SCP_STATUS_MAP: dict[str, VPSStatus] = {
    "NOSTATE": VPSStatus.UNKNOWN,
    "RUNNING": VPSStatus.RUNNING,
    "BLOCKED": VPSStatus.UNKNOWN,
    "PAUSED": VPSStatus.STOPPING,
    "SHUTDOWN": VPSStatus.STOPPING,
    "SHUTOFF": VPSStatus.STOPPED,
    "CRASHED": VPSStatus.STOPPED,
    "PMSUSPENDED": VPSStatus.UNKNOWN,
    "DISK_SNAPSHOT": VPSStatus.UNKNOWN,
}


def _status_from_netcup(value: str) -> VPSStatus:
    return _SCP_STATUS_MAP.get(value, VPSStatus.UNKNOWN)


@dataclass
class NetcupProvider(VPSProvider):
    http: Any
    access_token: str
    base_url: str = "https://www.servercontrolpanel.de/scp-core/api/v1"
    provider_name: str = "netcup"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }

    def _handle_error(self, status_code: int, body: str) -> None:
        if status_code in (401, 403):
            raise ProviderAuthError("Netcup SCP authentication failed")
        if status_code == 404:
            raise ProviderNotFoundError("VPS not found")
        raise ProviderError(f"Netcup SCP API error: {status_code}")

    def _get(self, path: str) -> Any:
        url = f"{self.base_url}{path}"
        resp = self.http.get(url, headers=self._headers())
        if resp.status_code not in (200, 201, 204):
            body = resp.body.decode("utf-8") if hasattr(resp, "body") and resp.body else ""
            self._handle_error(resp.status_code, body)
        return resp.json()

    def _server_to_vps(self, srv: dict[str, Any]) -> VPS:
        live_info = srv.get("serverLiveInfo") or {}
        ipv4_list = srv.get("ipv4Addresses") or []
        ipv6_list = srv.get("ipv6Addresses") or []
        site = srv.get("site") or {}
        template = srv.get("template") or {}

        ipv4 = ipv4_list[0].get("ip") if ipv4_list else None
        ipv6 = ipv6_list[0].get("networkPrefix") if ipv6_list else None

        state_str = live_info.get("state", "") or ""
        status = _status_from_netcup(state_str)

        vcpu = live_info.get("cpuCount")
        if vcpu is None:
            vcpu = srv.get("maxCpuCount")

        memory_mb = live_info.get("maxServerMemoryInMiB")
        if memory_mb is None:
            memory_mb = live_info.get("currentServerMemoryInMiB")

        disks = live_info.get("disks") or []
        total_mib = sum(d.get("capacityInMiB", 0) for d in disks if isinstance(d, dict))
        disk_gb = int(round(total_mib / 1024)) if total_mib else None

        plan = template.get("name") if isinstance(template, dict) else None

        return VPS(
            provider=self.provider_name,
            id=str(srv.get("id", "")),
            name=srv.get("name") or "",
            region=site.get("city") if isinstance(site, dict) and site.get("city") else None,
            status=status,
            ipv4=ipv4,
            ipv6=ipv6,
            vcpu=int(vcpu) if isinstance(vcpu, int) and not isinstance(vcpu, bool) else None,
            memory_mb=int(memory_mb) if isinstance(memory_mb, (int, float)) and not isinstance(memory_mb, bool) else None,
            disk_gb=disk_gb,
            bandwidth_gb=None,
            plan=str(plan) if isinstance(plan, str) and plan.strip() else None,
        )

    def list_vps(self) -> list[VPS]:
        data = self._get("/servers?limit=1000")
        if not isinstance(data, list):
            raise ProviderError(f"Unexpected response from Netcup SCP: expected list, got {type(data).__name__}")

        out: list[VPS] = []
        for item in data:
            server_id = item.get("id")
            if server_id is None:
                continue
            try:
                srv = self._get(f"/servers/{server_id}?loadServerLiveInfo=true")
                out.append(self._server_to_vps(srv))
            except (ProviderNotFoundError, ProviderError):
                continue
        return out

    def get_vps(self, *, id: Optional[str] = None, name: Optional[str] = None) -> VPS:
        if id:
            srv = self._get(f"/servers/{id}?loadServerLiveInfo=true")
            return self._server_to_vps(srv)

        if name:
            data = self._get(f"/servers?name={name}")
            if not isinstance(data, list):
                raise ProviderError(f"Unexpected response from Netcup SCP: expected list, got {type(data).__name__}")
            for item in data:
                item_name = item.get("name") or ""
                if item_name == name:
                    server_id = item.get("id")
                    if server_id is None:
                        continue
                    srv = self._get(f"/servers/{server_id}?loadServerLiveInfo=true")
                    return self._server_to_vps(srv)
            raise ProviderNotFoundError(f"VPS with name '{name}' not found")

        raise ProviderNotFoundError("VPS not found: provide id or name")

    def create_vps(
        self,
        *,
        name: str,
        region: str,
        server_type: str,
        image: str,
        ssh_keys: list[str],
    ) -> VPS:
        raise ProviderError("Netcup SCP API does not support VPS creation")

    def delete_vps(self, *, id: Optional[str] = None, name: Optional[str] = None) -> None:
        raise ProviderError("Netcup SCP API does not support VPS deletion")