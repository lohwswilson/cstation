from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

from cstation.providers.base import VPS, VPSProvider, VPSStatus


CONFIG_VPS_DIR = Path("config/vps")


@dataclass
class StaticProvider(VPSProvider):
    provider_name: str = "static"

    def list_vps(self) -> list[VPS]:
        results: list[VPS] = []
        if not CONFIG_VPS_DIR.is_dir():
            return results
        for entry in sorted(CONFIG_VPS_DIR.iterdir()):
            if not entry.is_dir():
                continue
            vps_yaml = entry / "vps.yaml"
            if not vps_yaml.exists():
                continue
            try:
                with vps_yaml.open("r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            if data.get("kind") != "VPS":
                continue
            identity = data.get("identity", {})
            if not isinstance(identity, dict):
                continue
            provider = identity.get("provider")
            if provider is not None and provider != "static":
                continue
            access = data.get("access", {})
            if not isinstance(access, dict):
                access = {}
            results.append(VPS(
                provider="static",
                id=identity.get("name", entry.name),
                name=identity.get("name", entry.name),
                region=identity.get("region"),
                status=VPSStatus.RUNNING,
                ipv4=access.get("host"),
            ))
        return results

    def get_vps(self, *, id: Optional[str] = None, name: Optional[str] = None) -> VPS:
        host = id or name
        if not host:
            from cstation.providers.errors import ProviderError
            raise ProviderError("Host or IP must be provided for static provider")

        return VPS(
            provider=self.provider_name,
            id=host,
            name=host,
            region="manual",
            status=VPSStatus.RUNNING,
            ipv4=host,
            ipv6=None,
        )

    def _is_ip(self, host: str) -> bool:
        import re
        return bool(re.match(r"^\d{1,3}(\.\d{1,3}){3}$", host))

    def create_vps(self, **kwargs) -> VPS:
        from cstation.providers.errors import ProviderError
        raise ProviderError("Static provider does not support creating VPS")

    def delete_vps(self, **kwargs) -> None:
        from cstation.providers.errors import ProviderError
        raise ProviderError("Static provider does not support deleting VPS")
