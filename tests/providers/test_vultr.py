from unittest.mock import Mock

from cstation.providers.vultr import VultrProvider


def test_get_vps_parses_allocated_resources():
    http = Mock()
    http.get.return_value.status_code = 200
    http.get.return_value.json.return_value = {
        "instance": {
            "id": "abc",
            "label": "vbox",
            "region": "ewr",
            "status": "active",
            "main_ip": "5.6.7.8",
            "v6_main_ip": "2001:db8::2",
            "vcpu_count": 2,
            "ram": 4096,
            "disk": 80,
            "allowed_bandwidth": 2000,
            "plan": "vc2-1c-2gb",
        }
    }

    p = VultrProvider(token="secret", http=http)
    v = p.get_vps(id="abc")
    assert v.vcpu == 2
    assert v.memory_mb == 4096
    assert v.disk_gb == 80
    assert v.bandwidth_gb == 2000
    assert v.plan == "vc2-1c-2gb"
