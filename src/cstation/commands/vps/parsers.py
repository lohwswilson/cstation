#!/usr/bin/env python3
"""
Parsing helpers for VPS fact collection and package management.
"""

from __future__ import annotations

import json as jsonlib
from typing import Any, Optional

from cstation.ssh import SSHManager


def _parse_os_release(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in raw.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip().strip('"')
    return out


def _first_line(result: Any) -> str:
    if not result or not getattr(result, "stdout", ""):
        return ""
    lines = result.stdout.strip().splitlines()
    return lines[0].strip() if lines else ""


def _detect_package_manager(ssh: SSHManager, os_id: str, results: Optional[dict[str, str]] = None) -> str:
    if os_id in ("ubuntu", "debian"):
        return "apt"
    if os_id in ("centos", "rhel", "fedora", "rocky", "almalinux"):
        return "dnf"
    if os_id in ("alpine",):
        return "apk"
    
    if results:
        if results.get("pkg_apt"): return "apt"
        if results.get("pkg_dnf"): return "dnf"
        if results.get("pkg_yum"): return "yum"
        if results.get("pkg_apk"): return "apk"

    if _first_line(ssh.run("command -v apt-get")):
        return "apt"
    if _first_line(ssh.run("command -v dnf")):
        return "dnf"
    if _first_line(ssh.run("command -v yum")):
        return "yum"
    if _first_line(ssh.run("command -v apk")):
        return "apk"
    return "unknown"


def _check_packages_batch(mgr: str, packages: list[str]) -> str:
    """Build a single shell command to check multiple packages."""
    cmds = []
    for p in packages:
        if mgr == "apt":
            cmds.append(f"dpkg -s {p} >/dev/null 2>&1 && echo 'inst:{p}' || echo 'miss:{p}'")
        elif mgr in ("dnf", "yum"):
            cmds.append(f"rpm -q {p} >/dev/null 2>&1 && echo 'inst:{p}' || echo 'miss:{p}'")
        elif mgr == "apk":
            cmds.append(f"apk info -e {p} >/dev/null 2>&1 && echo 'inst:{p}' || echo 'miss:{p}'")
    return " ; ".join(cmds)


def _package_installed(ssh: SSHManager, mgr: str, name: str) -> bool:
    if mgr == "apt":
        return _first_line(ssh.run(f"dpkg -s {name} >/dev/null 2>&1; echo $?")) == "0"
    if mgr in ("dnf", "yum"):
        return _first_line(ssh.run(f"rpm -q {name} >/dev/null 2>&1; echo $?")) == "0"
    if mgr == "apk":
        return _first_line(ssh.run(f"apk info -e {name} >/dev/null 2>&1; echo $?")) == "0"
    return False


def _parse_lscpu(raw: str) -> dict[str, Any]:
    """Parse lscpu output into structured fields."""
    fields: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()

    def _int_or_none(key: str) -> Optional[int]:
        v = fields.get(key, "")
        if not v:
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    return {
        "architecture": fields.get("Architecture"),
        "vendor": fields.get("Vendor ID") or fields.get("BIOS Vendor ID"),
        "model": fields.get("Model name") or fields.get("BIOS Model name"),
        "vcpu": _int_or_none("CPU(s)"),
        "cores_per_socket": _int_or_none("Core(s) per socket"),
        "sockets": _int_or_none("Socket(s)"),
        "threads_per_core": _int_or_none("Thread(s) per core"),
    }


def _parse_free_m(raw: str) -> dict[str, Any]:
    """Parse free -m output into structured fields."""
    lines = raw.strip().splitlines()
    result: dict[str, Any] = {}

    for line in lines:
        parts = line.split()
        if not parts:
            continue
        label = parts[0].rstrip(":")
        if label == "Mem" and len(parts) >= 3:
            try:
                result["total_mb"] = int(parts[1])
                result["used_mb"] = int(parts[2])
                result["available_mb"] = int(parts[6]) if len(parts) > 6 else None
            except (ValueError, IndexError):
                pass
        elif label == "Swap" and len(parts) >= 3:
            try:
                result["swap_total_mb"] = int(parts[1])
                result["swap_used_mb"] = int(parts[2])
            except (ValueError, IndexError):
                pass

    return result


def _parse_lsblk_json(raw: str) -> list[dict[str, Any]]:
    """Parse lsblk -b -J output into structured disk entries."""
    try:
        data = jsonlib.loads(raw) if raw else {}
    except (jsonlib.JSONDecodeError, ValueError):
        return []

    devices = data.get("blockdevices", [])
    result: list[dict[str, Any]] = []

    def _size_gb(size_bytes: Any) -> Optional[float]:
        if not isinstance(size_bytes, (int, float)) or isinstance(size_bytes, bool):
            return None
        return round(size_bytes / (1024**3), 1)

    def _partition(entry: dict[str, Any]) -> dict[str, Any]:
        mountpoints = entry.get("mountpoints", [])
        mount = None
        for mp in mountpoints:
            if mp is not None:
                mount = mp
                break
        if mount is None:
            mount = entry.get("mountpoint")
        child: dict[str, Any] = {
            "name": entry.get("name"),
            "size_gb": _size_gb(entry.get("size")),
            "type": entry.get("type"),
        }
        if mount:
            child["mountpoint"] = mount
        return child

    for dev in devices:
        entry: dict[str, Any] = {
            "name": dev.get("name"),
            "size_gb": _size_gb(dev.get("size")),
            "type": dev.get("type"),
        }
        mp = dev.get("mountpoint")
        mps = dev.get("mountpoints", [])
        for m in mps:
            if m is not None:
                mp = m
                break
        if mp:
            entry["mountpoint"] = mp
        children = dev.get("children", [])
        if children:
            entry["partitions"] = [_partition(c) for c in children]
        result.append(entry)

    return result


def _parse_ip_addr_json(raw: str) -> list[dict[str, Any]]:
    """Parse ip -j a output into structured interface list."""
    try:
        data = jsonlib.loads(raw) if raw else []
    except (jsonlib.JSONDecodeError, ValueError):
        return []
    if not isinstance(data, list):
        return []

    result: list[dict[str, Any]] = []
    for iface in data:
        if iface.get("ifname") == "lo":
            continue
        entry: dict[str, Any] = {
            "name": iface.get("ifname"),
            "state": iface.get("operstate"),
            "mac": iface.get("address"),
        }
        addr_info = iface.get("addr_info", [])
        for addr in addr_info:
            family = addr.get("family")
            if family == "inet" and not entry.get("ipv4"):
                entry["ipv4"] = addr.get("local")
                prefix = addr.get("prefixlen")
                if prefix is not None:
                    entry["ipv4_prefix"] = prefix
            elif family == "inet6" and not entry.get("ipv6"):
                addr_local = addr.get("local", "")
                if not addr_local.startswith("fe80:"):
                    entry["ipv6"] = addr_local
                    prefix = addr.get("prefixlen")
                    if prefix is not None:
                        entry["ipv6_prefix"] = prefix
        result.append(entry)

    return result


def _parse_ip_route(raw: str) -> list[dict[str, Any]]:
    """Parse ip route output into structured route entries."""
    result: list[dict[str, Any]] = []
    for line in raw.strip().splitlines():
        if not line.strip():
            continue
        parts = line.split()
        entry: dict[str, Any] = {"destination": parts[0] if parts else None}
        try:
            via_idx = parts.index("via")
            entry["via"] = parts[via_idx + 1] if via_idx + 1 < len(parts) else None
        except ValueError:
            pass
        try:
            dev_idx = parts.index("dev")
            entry["dev"] = parts[dev_idx + 1] if dev_idx + 1 < len(parts) else None
        except ValueError:
            pass
        result.append(entry)
    return result

