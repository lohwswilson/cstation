from __future__ import annotations

import json as jsonlib
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Optional

from cstation.providers.errors import ProviderAuthError, ProviderError, ProviderNotFoundError


@dataclass
class DNSRecord:
    id: Optional[str] = None
    domain: str = ""
    name: str = ""
    type: str = ""
    content: str = ""
    ttl: int = 1
    priority: Optional[int] = None
    proxied: bool = False
    comment: str = ""

    def to_api_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": self.name,
            "type": self.type,
            "content": self.content,
            "ttl": self.ttl,
            "proxied": self.proxied,
        }
        if self.priority is not None:
            d["priority"] = self.priority
        return d

    @classmethod
    def from_api(cls, data: dict[str, Any], domain: str = "") -> DNSRecord:
        return cls(
            id=str(data.get("id", "")),
            domain=domain,
            name=data.get("name", ""),
            type=data.get("type", ""),
            content=data.get("content", ""),
            ttl=data.get("ttl", 1),
            priority=data.get("priority"),
            proxied=data.get("proxied", False),
            comment=data.get("comment", ""),
        )


@dataclass
class DNSZone:
    id: str = ""
    name: str = ""
    status: str = ""

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> DNSZone:
        return cls(
            id=str(data.get("id", "")),
            name=data.get("name", ""),
            status=data.get("status", ""),
        )


@dataclass
class CloudflareProvider:
    api_token: str
    http: Any
    base_url: str = "https://api.cloudflare.com/client/v4"
    _zone_name_map: dict[str, str] = field(default_factory=dict)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, *, body: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}/{path}"
        data = jsonlib.dumps(body).encode("utf-8") if body else None
        req = urllib.request.Request(url, data=data, method=method, headers=self._headers())
        try:
            with urllib.request.urlopen(req) as resp:
                return jsonlib.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            if e.code in (401, 403):
                raise ProviderAuthError(f"Cloudflare authentication failed: {error_body}")
            raise ProviderError(f"Cloudflare API error {e.code}: {error_body}")
        except urllib.error.URLError as e:
            raise ProviderError(f"Cloudflare API connection error: {e.reason}")

    def list_zones(self) -> list[DNSZone]:
        result = self._request("GET", "zones?per_page=100")
        if not result.get("success"):
            raise ProviderError(f"Failed to list zones: {result.get('errors', [])}")
        return [DNSZone.from_api(z) for z in result.get("result", [])]

    def get_zone_id(self, domain: str) -> str:
        domain = domain.rstrip(".")
        parts = domain.split(".")
        for i in range(len(parts) - 1):
            candidate = ".".join(parts[i:])
            result = self._request("GET", f"zones?name={candidate}")
            if not result.get("success"):
                continue
            zones = result.get("result", [])
            if zones:
                self._zone_name_map[domain] = candidate
                return str(zones[0]["id"])
        raise ProviderNotFoundError(f"Cloudflare zone not found for domain: {domain}")

    def list_records(self, zone_id: str, domain: str = "") -> list[DNSRecord]:
        result = self._request("GET", f"zones/{zone_id}/dns_records?per_page=5000")
        if not result.get("success"):
            raise ProviderError(f"Failed to list records for zone {zone_id}: {result.get('errors', [])}")
        records = [DNSRecord.from_api(r, domain=domain) for r in result.get("result", [])]
        zone_name = self._zone_name_map.get(domain, domain)
        if zone_name != domain and zone_name:
            suffix = f".{zone_name}"
            filtered = []
            for r in records:
                if r.name == zone_name or r.name.endswith(suffix):
                    filtered.append(r)
            return filtered
        return records

    def create_record(self, zone_id: str, record: DNSRecord) -> DNSRecord:
        result = self._request("POST", f"zones/{zone_id}/dns_records", body=record.to_api_dict())
        if not result.get("success"):
            errors = result.get("errors", [])
            raise ProviderError(f"Failed to create DNS record {record.type} {record.name}: {errors}")
        return DNSRecord.from_api(result["result"], domain=record.domain)

    def update_record(self, zone_id: str, record_id: str, record: DNSRecord) -> DNSRecord:
        result = self._request("PUT", f"zones/{zone_id}/dns_records/{record_id}", body=record.to_api_dict())
        if not result.get("success"):
            errors = result.get("errors", [])
            raise ProviderError(f"Failed to update DNS record {record.type} {record.name}: {errors}")
        return DNSRecord.from_api(result["result"], domain=record.domain)

    def delete_record(self, zone_id: str, record_id: str) -> bool:
        result = self._request("DELETE", f"zones/{zone_id}/dns_records/{record_id}")
        if not result.get("success"):
            errors = result.get("errors", [])
            raise ProviderError(f"Failed to delete DNS record {record_id}: {errors}")
        return True

    def verify_token(self) -> bool:
        try:
            result = self._request("GET", "user/tokens/verify")
            return result.get("success", False)
        except ProviderAuthError:
            return False