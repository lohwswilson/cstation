"""Unit tests for the VPS parsing helpers (src/cstation/commands/vps/parsers.py)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from cstation.commands.vps.parsers import (
    _check_packages_batch,
    _detect_package_manager,
    _first_line,
    _package_installed,
    _parse_free_m,
    _parse_ip_addr_json,
    _parse_ip_route,
    _parse_lsblk_json,
    _parse_lscpu,
    _parse_os_release,
)


class _FakeResult:
    def __init__(self, stdout: str):
        self.stdout = stdout


class _FakeSSH:
    """SSH double whose run() returns canned stdout per exact command."""

    def __init__(self, responses: dict[str, str]):
        self.responses = responses

    def run(self, command: str, **kwargs):
        return _FakeResult(self.responses.get(command, ""))


# ---------------------------------------------------------------------------
# _parse_os_release
# ---------------------------------------------------------------------------

def test_parse_os_release_basic():
    raw = 'NAME="Ubuntu"\nVERSION_ID="22.04"\nID=ubuntu\nHOME_URL=https://example.com\n'
    assert _parse_os_release(raw) == {
        "NAME": "Ubuntu",
        "VERSION_ID": "22.04",
        "ID": "ubuntu",
        "HOME_URL": "https://example.com",
    }


def test_parse_os_release_skips_malformed_lines():
    raw = "no-equals-here\n\nID=debian\n"
    assert _parse_os_release(raw) == {"ID": "debian"}


def test_parse_os_release_empty():
    assert _parse_os_release("") == {}


# ---------------------------------------------------------------------------
# _first_line
# ---------------------------------------------------------------------------

def test_first_line_returns_trimmed_first_line():
    assert _first_line(_FakeResult("  hello \nworld\n")) == "hello"


def test_first_line_empty_for_none_result():
    assert _first_line(None) == ""


def test_first_line_empty_for_blank_stdout():
    assert _first_line(_FakeResult("   \n")) == ""


# ---------------------------------------------------------------------------
# _detect_package_manager
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "os_id,expected",
    [
        ("ubuntu", "apt"),
        ("debian", "apt"),
        ("centos", "dnf"),
        ("rhel", "dnf"),
        ("fedora", "dnf"),
        ("rocky", "dnf"),
        ("almalinux", "dnf"),
        ("alpine", "apk"),
    ],
)
def test_detect_package_manager_from_os_id(os_id, expected):
    assert _detect_package_manager(_FakeSSH({}), os_id) == expected


def test_detect_package_manager_from_batch_results():
    ssh = _FakeSSH({})
    assert _detect_package_manager(ssh, "unknown-os", {"pkg_apt": "1"}) == "apt"
    assert _detect_package_manager(ssh, "unknown-os", {"pkg_dnf": "1"}) == "dnf"
    assert _detect_package_manager(ssh, "unknown-os", {"pkg_yum": "1"}) == "yum"
    assert _detect_package_manager(ssh, "unknown-os", {"pkg_apk": "1"}) == "apk"


def test_detect_package_manager_probes_ssh_in_order():
    ssh = _FakeSSH({
        "command -v apt-get": "",
        "command -v dnf": "",
        "command -v yum": "/usr/bin/yum",
    })
    assert _detect_package_manager(ssh, "unknown-os") == "yum"


def test_detect_package_manager_unknown_when_no_manager_found():
    ssh = _FakeSSH({})
    assert _detect_package_manager(ssh, "unknown-os") == "unknown"


# ---------------------------------------------------------------------------
# _check_packages_batch
# ---------------------------------------------------------------------------

def test_check_packages_batch_apt():
    cmd = _check_packages_batch("apt", ["docker", "git"])
    assert cmd == (
        "dpkg -s docker >/dev/null 2>&1 && echo 'inst:docker' || echo 'miss:docker'"
        " ; "
        "dpkg -s git >/dev/null 2>&1 && echo 'inst:git' || echo 'miss:git'"
    )


def test_check_packages_batch_dnf():
    cmd = _check_packages_batch("dnf", ["nginx"])
    assert "rpm -q nginx >/dev/null 2>&1" in cmd
    assert "inst:nginx" in cmd


def test_check_packages_batch_apk():
    cmd = _check_packages_batch("apk", ["curl"])
    assert "apk info -e curl >/dev/null 2>&1" in cmd


def test_check_packages_batch_empty_packages():
    assert _check_packages_batch("apt", []) == ""


# ---------------------------------------------------------------------------
# _package_installed
# ---------------------------------------------------------------------------

def test_package_installed_apt():
    ssh = _FakeSSH({"dpkg -s docker >/dev/null 2>&1; echo $?": "0"})
    assert _package_installed(ssh, "apt", "docker") is True


def test_package_installed_apt_missing():
    ssh = _FakeSSH({"dpkg -s docker >/dev/null 2>&1; echo $?": "1"})
    assert _package_installed(ssh, "apt", "docker") is False


def test_package_installed_unknown_manager():
    assert _package_installed(_FakeSSH({}), "pacman", "docker") is False


# ---------------------------------------------------------------------------
# _parse_lscpu
# ---------------------------------------------------------------------------

LSCPU_RAW = """\
Architecture:            x86_64
CPU op-mode(s):          32-bit, 64-bit
Vendor ID:               GenuineIntel
Model name:              Intel(R) Xeon(R) CPU E5-2680 v4 @ 2.40GHz
CPU(s):                  8
Core(s) per socket:      4
Socket(s):               2
Thread(s) per core:      1
"""


def test_parse_lscpu():
    parsed = _parse_lscpu(LSCPU_RAW)
    assert parsed == {
        "architecture": "x86_64",
        "vendor": "GenuineIntel",
        "model": "Intel(R) Xeon(R) CPU E5-2680 v4 @ 2.40GHz",
        "vcpu": 8,
        "cores_per_socket": 4,
        "sockets": 2,
        "threads_per_core": 1,
    }


def test_parse_lscpu_missing_fields_are_none():
    parsed = _parse_lscpu("Architecture: arm64\n")
    assert parsed["architecture"] == "arm64"
    assert parsed["vcpu"] is None
    assert parsed["vendor"] is None


def test_parse_lscpu_skips_lines_without_colon():
    assert _parse_lscpu("just some text\n")["model"] is None


# ---------------------------------------------------------------------------
# _parse_free_m
# ---------------------------------------------------------------------------

FREE_M_RAW = """\
              total        used        free      shared  buff/cache   available
Mem:          16000        3200        9000         100        3800       12000
Swap:          2048         512        1536
"""


def test_parse_free_m():
    parsed = _parse_free_m(FREE_M_RAW)
    assert parsed == {
        "total_mb": 16000,
        "used_mb": 3200,
        "available_mb": 12000,
        "swap_total_mb": 2048,
        "swap_used_mb": 512,
    }


def test_parse_free_m_missing_swap():
    parsed = _parse_free_m("Mem: 1024 512 512\n")
    assert parsed["total_mb"] == 1024
    assert "swap_total_mb" not in parsed


# ---------------------------------------------------------------------------
# _parse_lsblk_json
# ---------------------------------------------------------------------------

def test_parse_lsblk_json():
    raw = json_dumps({
        "blockdevices": [
            {
                "name": "vda",
                "size": 53687091200,  # 50 GiB
                "type": "disk",
                "mountpoints": ["/"],
                "children": [
                    {"name": "vda1", "size": 53685091328, "type": "part", "mountpoints": ["/"]},
                ],
            }
        ]
    })
    parsed = _parse_lsblk_json(raw)
    assert len(parsed) == 1
    disk = parsed[0]
    assert disk["name"] == "vda"
    assert disk["size_gb"] == 50.0
    assert disk["mountpoint"] == "/"
    assert disk["partitions"][0]["name"] == "vda1"


def test_parse_lsblk_json_invalid_json_returns_empty():
    assert _parse_lsblk_json("{not valid json") == []


def test_parse_lsblk_json_empty():
    assert _parse_lsblk_json("") == []


# ---------------------------------------------------------------------------
# _parse_ip_addr_json
# ---------------------------------------------------------------------------

def test_parse_ip_addr_json():
    raw = json_dumps([
        {"ifname": "lo", "operstate": "UNKNOWN", "address": "00:00:00:00:00:00",
         "addr_info": [{"family": "inet", "local": "127.0.0.1", "prefixlen": 8}]},
        {"ifname": "ens3", "operstate": "UP", "address": "52:54:00:aa:bb:cc",
         "addr_info": [
             {"family": "inet", "local": "1.2.3.4", "prefixlen": 24},
             {"family": "inet6", "local": "2a01:4f8:1:2::5", "prefixlen": 64},
             {"family": "inet6", "local": "fe80::5054:ff:feaa:bbcc", "prefixlen": 64},
         ]},
    ])
    parsed = _parse_ip_addr_json(raw)
    assert len(parsed) == 1  # loopback skipped
    iface = parsed[0]
    assert iface["name"] == "ens3"
    assert iface["state"] == "UP"
    assert iface["mac"] == "52:54:00:aa:bb:cc"
    assert iface["ipv4"] == "1.2.3.4"
    assert iface["ipv4_prefix"] == 24
    assert iface["ipv6"] == "2a01:4f8:1:2::5"  # link-local fe80:: filtered
    assert iface["ipv6_prefix"] == 64


def test_parse_ip_addr_json_invalid_json_returns_empty():
    assert _parse_ip_addr_json("nope") == []


# ---------------------------------------------------------------------------
# _parse_ip_route
# ---------------------------------------------------------------------------

def test_parse_ip_route():
    raw = "default via 10.0.0.1 dev ens3\n10.0.0.0/24 dev ens3 proto kernel scope link src 10.0.0.5\n"
    parsed = _parse_ip_route(raw)
    assert parsed == [
        {"destination": "default", "via": "10.0.0.1", "dev": "ens3"},
        {"destination": "10.0.0.0/24", "dev": "ens3"},
    ]


def test_parse_ip_route_blank_lines_skipped():
    assert _parse_ip_route(" \n\n") == []


def json_dumps(obj) -> str:
    import json

    return json.dumps(obj)
