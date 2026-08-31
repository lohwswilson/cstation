from unittest.mock import Mock

import pytest

from cstation.providers.base import VPSStatus
from cstation.providers.netcup import NetcupProvider
from cstation.providers.errors import ProviderError, ProviderNotFoundError, ProviderAuthError


def _make_http(get_response=None, status_code=200):
    http = Mock()
    resp = Mock()
    resp.status_code = status_code
    resp.json.return_value = get_response or {}
    if status_code not in (200, 201, 204):
        resp.body = b""
    http.get.return_value = resp
    return http


def test_get_vps_by_id_parses_server_fields():
    http = _make_http(
        get_response={
            "id": 12345,
            "name": "v2202604354651455383",
            "hostname": "us02.synercatalyst.com",
            "nickname": "US02",
            "disabled": False,
            "template": {"id": 7, "name": "VPS 2000 G8s"},
            "site": {"id": 1, "city": "Nuremberg"},
            "ipv4Addresses": [{"id": 1, "ip": "46.38.240.100", "netmask": "255.255.255.0", "gateway": "46.38.240.1"}],
            "ipv6Addresses": [
                {"id": 1, "networkPrefix": "2a03:4000:2:1::", "networkPrefixLength": 64, "gateway": "2a03:4000:2:1::1"}
            ],
            "maxCpuCount": 4,
            "disksAvailableSpaceInMiB": 512000,
            "snapshotCount": 0,
            "rescueSystemActive": False,
            "snapshotAllowed": True,
            "architecture": "AMD64",
            "serverLiveInfo": {
                "state": "RUNNING",
                "cpuCount": 4,
                "maxServerMemoryInMiB": 16384,
                "currentServerMemoryInMiB": 8192,
                "disks": [
                    {"dev": "vda", "driver": "VIRTIO", "capacityInMiB": 512000, "allocationInMiB": 25600},
                ],
                "interfaces": [],
                "bootorder": [],
                "autostart": True,
                "uefi": True,
                "uptimeInSeconds": 86400,
            },
        }
    )

    p = NetcupProvider(http=http, access_token="test-token")
    v = p.get_vps(id="12345")

    assert v.provider == "netcup"
    assert v.id == "12345"
    assert v.name == "v2202604354651455383"
    assert v.status == VPSStatus.RUNNING
    assert v.ipv4 == "46.38.240.100"
    assert v.ipv6 == "2a03:4000:2:1::"
    assert v.vcpu == 4
    assert v.memory_mb == 16384
    assert v.disk_gb == 500
    assert v.region == "Nuremberg"
    assert v.plan == "VPS 2000 G8s"


def test_get_vps_by_name_searches_list():
    list_resp = Mock()
    list_resp.status_code = 200
    list_resp.json.return_value = [
        {
            "id": 12345,
            "name": "v2202604354651455383",
            "hostname": None,
            "nickname": None,
            "disabled": False,
            "template": None,
        },
    ]

    detail_resp = Mock()
    detail_resp.status_code = 200
    detail_resp.json.return_value = {
        "id": 12345,
        "name": "v2202604354651455383",
        "site": {"id": 1, "city": "Nuremberg"},
        "ipv4Addresses": [{"id": 1, "ip": "46.38.240.100"}],
        "ipv6Addresses": [],
        "maxCpuCount": 4,
        "serverLiveInfo": {
            "state": "SHUTOFF",
            "cpuCount": 4,
            "maxServerMemoryInMiB": 16384,
            "currentServerMemoryInMiB": 0,
            "disks": [{"capacityInMiB": 512000, "allocationInMiB": 0, "dev": "vda", "driver": "VIRTIO"}],
        },
    }

    http = Mock()
    http.get.side_effect = [list_resp, detail_resp]

    p = NetcupProvider(http=http, access_token="test-token")
    v = p.get_vps(name="v2202604354651455383")

    assert v.name == "v2202604354651455383"
    assert v.status == VPSStatus.STOPPED
    assert v.ipv4 == "46.38.240.100"


def test_status_mapping():
    http = _make_http(
        get_response={
            "id": 1,
            "name": "test",
            "site": {},
            "ipv4Addresses": [],
            "ipv6Addresses": [],
            "serverLiveInfo": {"state": "PAUSED", "disks": []},
        }
    )
    p = NetcupProvider(http=http, access_token="test-token")
    v = p.get_vps(id="1")
    assert v.status == VPSStatus.STOPPING


def test_get_vps_not_found():
    http = Mock()
    resp = Mock()
    resp.status_code = 404
    resp.body = b"Not found"
    http.get.return_value = resp

    p = NetcupProvider(http=http, access_token="test-token")
    with pytest.raises(ProviderNotFoundError):
        p.get_vps(id="99999")


def test_get_vps_auth_error():
    http = Mock()
    resp = Mock()
    resp.status_code = 401
    resp.body = b"Unauthorized"
    http.get.return_value = resp

    p = NetcupProvider(http=http, access_token="bad-token")
    with pytest.raises(ProviderAuthError):
        p.get_vps(id="1")


def test_create_vps_raises():
    http = _make_http()
    p = NetcupProvider(http=http, access_token="test-token")
    with pytest.raises(ProviderError, match="does not support VPS creation"):
        p.create_vps(name="x", region="x", server_type="x", image="x", ssh_keys=[])


def test_delete_vps_raises():
    http = _make_http()
    p = NetcupProvider(http=http, access_token="test-token")
    with pytest.raises(ProviderError, match="does not support VPS deletion"):
        p.delete_vps(id="1")


def test_list_vps():
    list_resp = Mock()
    list_resp.status_code = 200
    list_resp.json.return_value = [
        {"id": 1, "name": "srv1", "hostname": None, "nickname": None, "disabled": False, "template": None},
        {"id": 2, "name": "srv2", "hostname": None, "nickname": None, "disabled": False, "template": None},
    ]

    detail1 = Mock()
    detail1.status_code = 200
    detail1.json.return_value = {
        "id": 1,
        "name": "srv1",
        "site": {"city": "Nuremberg"},
        "ipv4Addresses": [{"id": 1, "ip": "1.2.3.4"}],
        "ipv6Addresses": [],
        "serverLiveInfo": {
            "state": "RUNNING",
            "cpuCount": 2,
            "maxServerMemoryInMiB": 8192,
            "disks": [{"capacityInMiB": 256000}],
        },
    }

    detail2 = Mock()
    detail2.status_code = 200
    detail2.json.return_value = {
        "id": 2,
        "name": "srv2",
        "site": {"city": "Falkenstein"},
        "ipv4Addresses": [{"id": 2, "ip": "5.6.7.8"}],
        "ipv6Addresses": [],
        "serverLiveInfo": {
            "state": "SHUTOFF",
            "cpuCount": 4,
            "maxServerMemoryInMiB": 16384,
            "disks": [{"capacityInMiB": 512000}],
        },
    }

    http = Mock()
    http.get.side_effect = [list_resp, detail1, detail2]

    p = NetcupProvider(http=http, access_token="test-token")
    servers = p.list_vps()

    assert len(servers) == 2
    assert servers[0].name == "srv1"
    assert servers[0].status == VPSStatus.RUNNING
    assert servers[1].name == "srv2"
    assert servers[1].status == VPSStatus.STOPPED
