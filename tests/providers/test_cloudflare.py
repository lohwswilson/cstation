from __future__ import annotations

from unittest.mock import Mock
import pytest

from cstation.providers.cloudflare import CloudflareProvider, DNSRecord, DNSZone
from cstation.providers.errors import ProviderAuthError, ProviderError, ProviderNotFoundError


def _provider():
    return CloudflareProvider(api_token="test-token", http=Mock())


class TestDNSRecord:
    def test_to_api_dict_basic(self):
        r = DNSRecord(name="mail", type="A", content="1.2.3.4", ttl=300)
        d = r.to_api_dict()
        assert d == {
            "name": "mail",
            "type": "A",
            "content": "1.2.3.4",
            "ttl": 300,
            "proxied": False,
        }

    def test_to_api_dict_with_priority(self):
        r = DNSRecord(name="", type="MX", content="mail.example.com", ttl=300, priority=10)
        d = r.to_api_dict()
        assert d["priority"] == 10

    def test_to_api_dict_no_priority(self):
        r = DNSRecord(name="test", type="A", content="1.2.3.4", ttl=300)
        d = r.to_api_dict()
        assert "priority" not in d

    def test_from_api(self):
        data = {
            "id": "abc123",
            "name": "mail.example.com",
            "type": "A",
            "content": "1.2.3.4",
            "ttl": 300,
            "proxied": False,
            "priority": None,
            "comment": "cstation",
        }
        r = DNSRecord.from_api(data, domain="example.com")
        assert r.id == "abc123"
        assert r.domain == "example.com"
        assert r.name == "mail.example.com"
        assert r.type == "A"
        assert r.content == "1.2.3.4"
        assert r.ttl == 300

    def test_from_api_mx_with_priority(self):
        data = {
            "id": "def456",
            "name": "example.com",
            "type": "MX",
            "content": "mail.example.com",
            "ttl": 300,
            "proxied": False,
            "priority": 10,
        }
        r = DNSRecord.from_api(data, domain="example.com")
        assert r.priority == 10

    def test_from_api_root_record(self):
        data = {
            "id": "rr1",
            "name": "example.com",
            "type": "MX",
            "content": "mail.example.com",
            "ttl": 300,
            "proxied": False,
            "priority": 10,
        }
        r = DNSRecord.from_api(data, domain="example.com")
        assert r.name == "example.com"
        assert r.priority == 10

    def test_srv_to_api_dict(self):
        r = DNSRecord(
            name="_imaps._tcp.example.com",
            type="SRV",
            content="mail.example.com",
            priority=1,
            srv_weight=1,
            srv_port=993
        )
        d = r.to_api_dict()
        assert "content" not in d
        assert d["data"]["priority"] == 1
        assert d["data"]["weight"] == 1
        assert d["data"]["port"] == 993
        assert d["data"]["target"] == "mail.example.com"
        assert d["data"]["service"] == "_imaps"
        assert d["data"]["proto"] == "_tcp"
        assert d["data"]["name"] == "example.com"

    def test_srv_from_api(self):
        data = {
            "id": "srv1",
            "name": "_imaps._tcp.example.com",
            "type": "SRV",
            "content": "1 993 mail.example.com",
            "data": {
                "priority": 1,
                "weight": 2,
                "port": 993,
                "target": "mail.example.com",
                "service": "_imaps",
                "proto": "_tcp",
                "name": "example.com"
            },
            "ttl": 300
        }
        r = DNSRecord.from_api(data, domain="example.com")
        assert r.srv_weight == 2
        assert r.srv_port == 993
        assert r.content == "mail.example.com"
        assert r.priority == 1

    def test_srv_from_api_legacy_fallback(self):
        data = {
            "id": "srv1",
            "name": "_imaps._tcp.example.com",
            "type": "SRV",
            "content": "5 443 target.com",
            "ttl": 300,
            "priority": 10
        }
        r = DNSRecord.from_api(data, domain="example.com")
        assert r.srv_weight == 5
        assert r.srv_port == 443
        assert r.content == "target.com"
        assert r.priority == 10


class TestDNSZone:
    def test_from_api(self):
        data = {"id": "zone1", "name": "example.com", "status": "active"}
        z = DNSZone.from_api(data)
        assert z.id == "zone1"
        assert z.name == "example.com"
        assert z.status == "active"


class TestCloudflareProvider:
    def test_list_zones(self):
        p = _provider()
        p._request = Mock(return_value={
            "success": True,
            "result": [
                {"id": "z1", "name": "example.com", "status": "active"},
                {"id": "z2", "name": "example.org", "status": "active"},
            ],
        })
        zones = p.list_zones()
        assert len(zones) == 2
        assert zones[0].name == "example.com"
        p._request.assert_called_once_with("GET", "zones?per_page=100")

    def test_get_zone_id(self):
        p = _provider()
        p._request = Mock(return_value={
            "success": True,
            "result": [{"id": "zone123", "name": "example.com"}],
        })
        zone_id = p.get_zone_id("example.com")
        assert zone_id == "zone123"
        p._request.assert_called_once_with("GET", "zones?name=example.com")

    def test_get_zone_id_not_found(self):
        p = _provider()
        p._request = Mock(return_value={"success": True, "result": []})
        with pytest.raises(ProviderNotFoundError):
            p.get_zone_id("nonexistent.com")

    def test_list_records(self):
        p = _provider()
        p._request = Mock(return_value={
            "success": True,
            "result": [
                {"id": "r1", "name": "mail.example.com", "type": "A", "content": "1.2.3.4", "ttl": 300, "proxied": False, "priority": None},
                {"id": "r2", "name": "example.com", "type": "MX", "content": "mail.example.com", "ttl": 300, "proxied": False, "priority": 10},
            ],
        })
        records = p.list_records("zone123", domain="example.com")
        assert len(records) == 2
        assert records[0].type == "A"
        assert records[1].priority == 10
        p._request.assert_called_once_with("GET", "zones/zone123/dns_records?per_page=5000")

    def test_create_record(self):
        p = _provider()
        record = DNSRecord(name="mail", type="A", content="1.2.3.4", ttl=300, domain="example.com")
        p._request = Mock(return_value={
            "success": True,
            "result": {"id": "new1", "name": "mail.example.com", "type": "A", "content": "1.2.3.4", "ttl": 300, "proxied": False},
        })
        new_rec = p.create_record("zone123", record)
        assert new_rec.id == "new1"

    def test_update_record(self):
        p = _provider()
        record = DNSRecord(name="mail", type="A", content="5.6.7.8", ttl=300, domain="example.com")
        p._request = Mock(return_value={
            "success": True,
            "result": {"id": "existing1", "name": "mail.example.com", "type": "A", "content": "5.6.7.8", "ttl": 300, "proxied": False},
        })
        updated = p.update_record("zone123", "existing1", record)
        assert updated.content == "5.6.7.8"

    def test_delete_record(self):
        p = _provider()
        p._request = Mock(return_value={"success": True})
        assert p.delete_record("zone123", "rec1") is True

    def test_auth_error(self):
        p = _provider()
        p._request = Mock(side_effect=ProviderAuthError("Auth failed"))
        with pytest.raises(ProviderAuthError):
            p.list_zones()

    def test_verify_token_valid(self):
        p = _provider()
        p._request = Mock(return_value={"success": True})
        assert p.verify_token() is True

    def test_verify_token_invalid(self):
        p = _provider()
        p._request = Mock(side_effect=ProviderAuthError("Bad token"))
        assert p.verify_token() is False