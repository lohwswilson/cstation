from unittest.mock import Mock

from cstation.providers.base import VPSStatus
from cstation.providers.hetzner import HetznerProvider


def test_list_vps_parses_servers():
    http = Mock()
    http.get.return_value.status_code = 200
    http.get.return_value.json.return_value = {
        "servers": [
            {
                "id": 123,
                "name": "sg07",
                "status": "running",
                "datacenter": {"location": {"name": "hel1"}},
                "public_net": {"ipv4": {"ip": "1.2.3.4"}, "ipv6": {"ip": "2001:db8::1"}},
            }
        ]
    }

    p = HetznerProvider(token="secret", http=http)
    vps_list = p.list_vps()
    assert len(vps_list) == 1
    assert vps_list[0].name == "sg07"
    assert vps_list[0].status == VPSStatus.RUNNING
    http.get.assert_called()


def test_get_vps_parses_allocated_resources():
    http = Mock()
    http.get.return_value.status_code = 200
    http.get.return_value.json.return_value = {
        "server": {
            "id": 123,
            "name": "sg07",
            "status": "running",
            "datacenter": {"location": {"name": "hel1"}},
            "public_net": {"ipv4": {"ip": "1.2.3.4"}, "ipv6": {"ip": "2001:db8::1"}},
            "server_type": {
                "name": "cx21",
                "cores": 2,
                "memory": 4,
                "disk": 80,
                "included_traffic": 21990232555520,
            },
        }
    }

    p = HetznerProvider(token="secret", http=http)
    v = p.get_vps(id="123")
    assert v.vcpu == 2
    assert v.memory_mb == 4096
    assert v.disk_gb == 80
    assert v.bandwidth_gb == 20480
    assert v.plan == "cx21"
