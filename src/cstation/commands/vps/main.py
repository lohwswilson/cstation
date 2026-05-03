#!/usr/bin/env python3
"""
VPS command module for CStation CLI
"""

from __future__ import annotations

import json as jsonlib
import os
import re
import shutil
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import typer
import yaml
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from cstation.config import get_config
from cstation.ssh import SSHManager
from cstation.providers.hetzner import HetznerProvider
from cstation.providers.vultr import VultrProvider
from cstation.providers.static import StaticProvider
from cstation.providers.netcup import NetcupProvider
from cstation.providers.errors import ProviderAuthError, ProviderError, ProviderNotFoundError


console = Console()

KEY_PACKAGES = [
    "openssh-server",
    "ufw",
    "nftables",
    "fail2ban",
    "docker",
    "docker.io",
    "containerd",
    "docker-compose-v2",
    "python3",
    "rsync",
    "curl",
    "git",
    "sudo",
]


class _CStationYamlDumper(yaml.SafeDumper):
    pass


def _yaml_represent_str(dumper: yaml.SafeDumper, data: str) -> yaml.nodes.ScalarNode:
    style = "|" if "\n" in data else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


_CStationYamlDumper.add_representer(str, _yaml_represent_str)


@dataclass(frozen=True)
class _HttpResponse:
    status_code: int
    body: bytes

    def json(self) -> Any:
        if not self.body:
            return {}
        return jsonlib.loads(self.body.decode("utf-8"))


class _HttpClient:
    def get(self, url: str, *, headers: dict[str, str]) -> _HttpResponse:
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req) as resp:  # noqa: S310
                return _HttpResponse(status_code=resp.status, body=resp.read())
        except urllib.error.HTTPError as e:
            return _HttpResponse(status_code=int(e.code), body=e.read())

    def post(self, url: str, *, headers: dict[str, str], json: dict[str, Any]) -> _HttpResponse:
        body = jsonlib.dumps(json).encode("utf-8")
        req = urllib.request.Request(
            url,
            headers={**headers, "Content-Type": "application/json"},
            data=body,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as resp:  # noqa: S310
                return _HttpResponse(status_code=resp.status, body=resp.read())
        except urllib.error.HTTPError as e:
            return _HttpResponse(status_code=int(e.code), body=e.read())

    def delete(self, url: str, *, headers: dict[str, str]) -> _HttpResponse:
        req = urllib.request.Request(url, headers=headers, method="DELETE")
        try:
            with urllib.request.urlopen(req) as resp:  # noqa: S310
                return _HttpResponse(status_code=resp.status, body=resp.read())
        except urllib.error.HTTPError as e:
            return _HttpResponse(status_code=int(e.code), body=e.read())


vps_app = typer.Typer(name="vps", help="VPS lifecycle management", invoke_without_command=True)


def _strip_nulls(obj: Any) -> Any:
    """Recursively remove keys with None values from dicts, and None items from lists."""
    if isinstance(obj, dict):
        return {k: _strip_nulls(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_strip_nulls(item) for item in obj if item is not None]
    return obj


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
    return result.stdout.strip().splitlines()[0].strip()


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


def _collect_facts(ssh: SSHManager) -> dict[str, Any]:
    # Phase 1: Bundle all fact collection + package manager detection
    batch_cmds = {
        "os_release": "cat /etc/os-release",
        "kernel": "uname -r",
        "hostname": "hostname",
        "lscpu": "lscpu",
        "memory": "free -m",
        "lsblk": "lsblk -b -J",
        "ip_addr": "ip -j a",
        "ip_route": "ip route",
        "uptime": "uptime",
        "df": "df -h / --output=size,used,avail,pcent | tail -1",
        "docker_stats": "docker ps --format '{{.Status}}' 2>/dev/null",
        "pkg_apt": "command -v apt-get",
        "pkg_dnf": "command -v dnf",
        "pkg_yum": "command -v yum",
        "pkg_apk": "command -v apk",
    }
    
    results = ssh.run_batch(batch_cmds)
    
    os_release = _parse_os_release(results["os_release"])
    os_id = os_release.get("ID", "")
    pkg_mgr = _detect_package_manager(ssh, os_id, results)

    # Phase 2: Check all packages in a second batch now that we know the pkg_mgr
    pkg_results_raw = ""
    if pkg_mgr != "unknown":
        pkg_batch_cmd = _check_packages_batch(pkg_mgr, KEY_PACKAGES)
        pkg_res = ssh.run(pkg_batch_cmd)
        pkg_results_raw = getattr(pkg_res, "stdout", "") or ""
    
    detected = []
    for line in pkg_results_raw.splitlines():
        if line.startswith("inst:"):
            detected.append(line.split(":", 1)[1])
    
    missing = [p for p in KEY_PACKAGES if p not in detected]

    kernel = results["kernel"].strip()
    hostname = results["hostname"].strip()
    
    lscpu_raw = results["lscpu"]
    mem_raw = results["memory"]
    lsblk_raw = results["lsblk"]
    ip_addr_raw = results["ip_addr"]
    ip_route_raw = results["ip_route"]
    uptime_raw = results["uptime"]
    df_raw = results["df"]
    docker_stats = results["docker_stats"]

    parsed_cpu = _parse_lscpu(lscpu_raw) if lscpu_raw else {}
    parsed_memory = _parse_free_m(mem_raw) if mem_raw else {}
    parsed_disks = _parse_lsblk_json(lsblk_raw) if lsblk_raw else []
    parsed_interfaces = _parse_ip_addr_json(ip_addr_raw) if ip_addr_raw else []
    parsed_routes = _parse_ip_route(ip_route_raw) if ip_route_raw else []

    # Parse Load Avg
    load_avg = ""
    if "load average:" in uptime_raw:
        load_avg = uptime_raw.split("load average:")[1].strip()

    # Parse DF
    df_parts = df_raw.split()
    disk_usage = {
        "total": df_parts[0] if len(df_parts) > 0 else "?",
        "used": df_parts[1] if len(df_parts) > 1 else "?",
        "avail": df_parts[2] if len(df_parts) > 2 else "?",
        "percent": df_parts[3] if len(df_parts) > 3 else "?",
    }

    # Parse Docker Stats
    docker_summary = {"running": 0, "total": 0}
    if docker_stats:
        lines = docker_stats.strip().splitlines()
        docker_summary["total"] = len(lines)
        docker_summary["running"] = sum(1 for line in lines if "Up" in line)

    return {
        "os": {
            "id": os_release.get("ID"),
            "version": os_release.get("VERSION_ID"),
            "pretty": os_release.get("PRETTY_NAME"),
            "kernel": kernel,
            "package_manager": pkg_mgr,
        },
        "cpu": parsed_cpu,
        "memory": parsed_memory,
        "disks": parsed_disks,
        "disk_usage": disk_usage,
        "load_avg": load_avg,
        "docker_summary": docker_summary,
        "network": {
            "interfaces": parsed_interfaces,
            "routes": parsed_routes,
        },
        "hostname": hostname,
        "packages": {
            "detected": detected,
            "missing": missing,
        },
    }


def _config_accounts(provider: str) -> dict[str, str]:
    cfg = get_config()
    accounts = cfg.get_config_value(f"vps.providers.{provider}.accounts", default=None)
    if not accounts:
        if provider == "netcup":
            scp = cfg.get_config_value(f"vps.providers.{provider}.scp", default=None)
            if scp and isinstance(scp, dict):
                out: dict[str, str] = {}
                for name in scp:
                    if isinstance(scp[name], dict):
                        if scp[name].get("enabled", True):
                            out[str(name)] = "oauth"
                    else:
                        out[str(name)] = "oauth"
                if out:
                    return out
        return {}
    if not isinstance(accounts, dict):
        raise typer.BadParameter(f"Invalid config: vps.providers.{provider}.accounts must be a mapping")

    out: dict[str, str] = {}
    for name, value in accounts.items():
        if isinstance(value, str):
            token = value
        elif isinstance(value, dict):
            token = value.get("token")
        else:
            token = None
        if not isinstance(token, str) or not token.strip():
            raise typer.BadParameter(f"Invalid config: missing token for {provider} account '{name}'")
        out[str(name)] = token.strip()
    return out


def _default_provider() -> str:
    cfg = get_config()
    value = cfg.get_config_value("vps.default_provider", default="hetzner")
    if not isinstance(value, str) or not value.strip():
        return "hetzner"
    return value.strip()


def _configured_providers() -> list[str]:
    cfg = get_config()
    providers = cfg.get_config_value("vps.providers", default={}) or {}
    if not isinstance(providers, dict):
        providers = {}
    
    result = [str(k) for k in providers.keys()]
    
    if "static" not in result:
        result.append("static")
    return result


def _provider_from_token(provider: str, token: str) -> Any:
    if provider == "static":
        return StaticProvider()
    if provider == "hetzner":
        return HetznerProvider(token=token, http=_HttpClient())
    if provider == "vultr":
        return VultrProvider(token=token, http=_HttpClient())
    if provider == "netcup":
        from cstation.providers.netcup_auth import get_access_token, NetcupAuthError
        try:
            access_token = get_access_token()
        except NetcupAuthError as e:
            raise typer.BadParameter(f"Netcup SCP auth failed: {e}. Run 'cstation netcup auth-login' first.")
        return NetcupProvider(http=_HttpClient(), access_token=access_token)
    raise typer.BadParameter(f"Unsupported provider '{provider}'")


def _resolve_account(provider: str, account: Optional[str]) -> tuple[Optional[str], str]:
    if provider == "static":
        return account or "manual", "none"

    accounts = _config_accounts(provider)
    if accounts:
        if account is None:
            if len(accounts) == 1:
                (only_name, only_token), = accounts.items()
                return only_name, only_token
            raise typer.BadParameter(
                f"Multiple {provider} accounts configured; use --account or prefix target with <account>:"
            )
        if account not in accounts:
            raise typer.BadParameter(f"Unknown {provider} account '{account}'")
        return account, accounts[account]

    if provider == "hetzner":
        token = os.getenv("HETZNER_TOKEN")
        if token:
            return None, token

    if provider == "netcup":
        from cstation.providers.netcup_auth import credentials_exist
        if credentials_exist():
            return None, "oauth"
        raise typer.BadParameter(
            f"No Netcup SCP credentials found. Run 'cstation netcup auth-login' first, "
            f"or configure vps.providers.netcup.scp in ~/.config/cstation/config.yaml"
        )

    raise typer.BadParameter(
        f"Missing {provider} token; configure ~/.config/cstation/config.yaml (vps.providers.{provider}.accounts)"
    )


def _provider(provider: str, account: Optional[str]) -> tuple[Optional[str], Any]:
    resolved_account, token = _resolve_account(provider, account)
    return resolved_account, _provider_from_token(provider, token)


def _parse_target(target: str) -> tuple[Optional[str], Optional[str]]:
    if target.isdigit():
        return target, None
    if re.match(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", target):
        return target, None
    return None, target


def _split_account_target(target: str) -> tuple[Optional[str], str]:
    if ":" not in target:
        return None, target
    account, rest = target.split(":", 1)
    if not account or not rest:
        return None, target
    return account, rest


@vps_app.command("list")
def vps_list(
    provider: str = typer.Option("all"),
    account: Optional[str] = typer.Option(None, "--account"),
) -> None:
    """List all VPS instances from configured providers in parallel."""
    aggregate_mode = provider == "all" and account is None
    auth_errors: list[str] = []
    provider_errors: list[str] = []
    rows: list[tuple[str, Optional[str], Any]] = []

    providers = _configured_providers()
    if not providers and os.getenv("HETZNER_TOKEN"):
        providers = ["hetzner", "static"]
    if not providers:
        console.print(
            "[red]✗[/red] No VPS providers configured; set vps.providers in ~/.config/cstation/config.yml (or set HETZNER_TOKEN)"
        )
        raise typer.Exit(2)

    if provider != "all" and provider not in providers:
        if provider == "hetzner" and os.getenv("HETZNER_TOKEN"):
            providers = ["hetzner"]
        else:
            raise typer.BadParameter(f"Unknown provider '{provider}'")

    providers_to_list = providers if provider == "all" else [provider]
    
    # Prepare work units for parallel execution
    tasks = []
    for p_name in providers_to_list:
        accounts = _config_accounts(p_name)
        if accounts:
            if account is not None and account not in accounts:
                raise typer.BadParameter(f"Unknown {p_name} account '{account}'")
            for acct_name, token in accounts.items():
                if account is not None and acct_name != account:
                    continue
                tasks.append((p_name, acct_name, token))
        else:
            # For providers without accounts (like static or environment-based)
            tasks.append((p_name, None, None))

    def _fetch_vps_task(p_name: str, acct_name: Optional[str], token: Optional[str]):
        try:
            if token:
                p = _provider_from_token(p_name, token)
            else:
                acct_name, p = _provider(p_name, account=None)
            
            vps_list = p.list_vps()
            return p_name, acct_name, vps_list, None, None
        except ProviderAuthError as e:
            return p_name, acct_name, [], f"{p_name}{'/' + acct_name if acct_name else ''}: {e}", None
        except ProviderError as e:
            return p_name, acct_name, [], None, f"{p_name}{'/' + acct_name if acct_name else ''}: {e}"
        except Exception as e:
            return p_name, acct_name, [], None, f"{p_name}{'/' + acct_name if acct_name else ''}: unexpected error: {e}"

    # Execute discovery in parallel
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(_fetch_vps_task, *t) for t in tasks]
        for future in futures:
            p_name, acct_name, vps_list, auth_err, prov_err = future.result()
            
            if auth_err:
                if not aggregate_mode:
                    console.print(f"[red]✗[/red] {auth_err}")
                    raise typer.Exit(2)
                auth_errors.append(auth_err)
            
            if prov_err:
                if not aggregate_mode:
                    console.print(f"[red]✗[/red] {prov_err}")
                    raise typer.Exit(1)
                provider_errors.append(prov_err)
            
            for v in vps_list:
                rows.append((p_name, acct_name, v))

    if not rows:
        if auth_errors:
            for msg in auth_errors:
                console.print(f"[red]✗[/red] {msg}")
            raise typer.Exit(2)
        if provider_errors:
            for msg in provider_errors:
                console.print(f"[red]✗[/red] {msg}")
            raise typer.Exit(1)
        console.print("[dim]No VPS instances found.[/dim]")
        return

    table = Table(title="VPS")
    distinct_providers = sorted({p for p, _, _ in rows})
    show_provider = len(distinct_providers) > 1
    show_account = any(acct is not None for _, acct, _ in rows)

    if show_provider:
        table.add_column("Provider")
    if show_account:
        table.add_column("Account")
    table.add_column("ID", overflow="fold")
    table.add_column("Name")
    table.add_column("Region")
    table.add_column("Status")
    table.add_column("IPv4")
    for provider_name, acct_name, v in rows:
        if show_provider and acct_name:
            id_value = v.id
        elif show_provider and not acct_name:
            id_value = v.id
        elif show_account and acct_name:
            id_value = f"{acct_name}:{v.id}"
        else:
            id_value = v.id

        row: list[str] = []
        if show_provider:
            row.append(provider_name)
        if show_account:
            row.append(acct_name or "-")
        row.extend([id_value, v.name, v.region or "-", v.status.value, v.ipv4 or "-"])
        table.add_row(*row)
    console.print(table)
    for msg in auth_errors:
        console.print(f"[yellow]![/yellow] {msg}")
    for msg in provider_errors:
        console.print(f"[yellow]![/yellow] {msg}")


@vps_app.command("status")
def vps_status(
    target: str = typer.Argument(..., help="VPS name (e.g. sg01.synercatalyst.com) or target in the form <provider>/<account>:<id>"),
    provider: Optional[str] = typer.Option(None, "--provider"),
    account: Optional[str] = typer.Option(None, "--account"),
) -> None:
    """Show detailed live status for a specific VPS instance via SSH."""
    # Try to resolve as a local VPS name first (silent check)
    vps_dir = Path("config/vps") / target
    if vps_dir.is_dir() and (vps_dir / "vps.yaml").exists():
        try:
            vps_data = _load_vps_config(vps_dir)
            identity = vps_data.get("identity", {})
            target_name = identity.get("name", vps_dir.name)
            
            if "access" in vps_data:
                access = vps_data.get("access", {})
                host = access.get("host")
                if host:
                    console.print(f"Connecting to [bold]{target_name}[/bold] via SSH to collect live status...")
                    ssh = _ssh_from_config(vps_data)
                    facts = _collect_facts(ssh)
                    if not facts or not facts.get("os", {}).get("id"):
                        console.print("[yellow]⚠[/yellow] Failed to collect comprehensive facts. Check SSH connectivity.")
                    _print_vps_live_status(target_name, identity.get("region", "manual"), access, facts)
                    return
                else:
                    console.print("[red]✗[/red] VPS config missing access.host")
                    raise typer.Exit(1)
        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Failed to get live status via SSH: {e}")
            # Fall through to provider logic as fallback

    # Fallback to manual provider/account:id logic
    target_provider, rest = (target.split("/", 1) + [None])[:2] if "/" in target else (None, target)
    if target_provider is not None and provider is not None and target_provider != provider:
        raise typer.BadParameter("Conflicting provider selection: both --provider and <provider>/<target> were provided")
    
    effective_provider = (target_provider or provider or _default_provider()).strip()
    target_account, raw_target = _split_account_target(rest)
    
    if target_account is not None and account is not None and target_account != account:
        raise typer.BadParameter("Conflicting account selection: both --account and <account>:<target> were provided")
    effective_account = target_account or account

    id_, name = _parse_target(raw_target)
    try:
        _, p = _provider(effective_provider, effective_account)
        v = p.get_vps(id=id_, name=name)
        _print_vps_status_table(v)
    except ProviderNotFoundError as e:
        console.print(f"[red]✗[/red] {e}")
        console.print("[dim]If this is a managed server, ensure its directory name in config/vps/ matches exactly.[/dim]")
        raise typer.Exit(3)
    except ProviderAuthError as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(2)
    except ProviderError as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(1)


def _print_vps_status_table(v: Any) -> None:
    table = Table(title="VPS Status")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("ID", v.id)
    table.add_row("Name", v.name)
    if v.region is not None:
        table.add_row("Region", v.region)
    table.add_row("Status", v.status.value)
    if v.ipv4 is not None:
        table.add_row("IPv4", v.ipv4)
    if v.ipv6 is not None:
        table.add_row("IPv6", v.ipv6)
    if v.vcpu is not None:
        table.add_row("vCPU", str(v.vcpu))
    if v.memory_mb is not None:
        table.add_row("Memory (MB)", str(v.memory_mb))
    if v.disk_gb is not None:
        table.add_row("Disk (GB)", str(v.disk_gb))
    if v.bandwidth_gb is not None:
        table.add_row("Bandwidth (GB)", str(v.bandwidth_gb))
    if v.plan is not None:
        table.add_row("Plan", v.plan)
    console.print(table)


def _print_vps_live_status(name: str, region: str, access: dict, facts: dict) -> None:
    table = Table(title=f"VPS Live Status: {name}", show_header=False)
    table.add_column("Field", style="bold cyan")
    table.add_column("Value")
    
    table.add_row("Name", name)
    table.add_row("Region", region)
    table.add_row("Status", "[green]running[/green]")
    table.add_row("IPv4", access.get("host", "-"))
    
    table.add_section()
    os_info = facts.get("os", {})
    table.add_row("OS", os_info.get("pretty", "-"))
    table.add_row("Kernel", os_info.get("kernel", "-"))
    table.add_row("Load Avg", facts.get("load_avg", "-"))
    
    table.add_section()
    cpu = facts.get("cpu", {})
    if cpu:
        cpu_val = f"{cpu.get('vcpu', '?')} vCPUs ({cpu.get('model', '?')})"
        table.add_row("CPU", cpu_val)
        
    mem = facts.get("memory", {})
    if mem:
        total = mem.get("total_mb", 0)
        used = mem.get("used_mb", 0)
        pct = (used / total * 100) if total > 0 else 0
        table.add_row("Memory", f"{used} MB / {total} MB ({pct:.1f}%)")
        
        swap_total = mem.get("swap_total_mb", 0)
        if swap_total > 0:
            swap_used = mem.get("swap_used_mb", 0)
            swap_pct = (swap_used / swap_total * 100)
            table.add_row("Swap", f"{swap_used} MB / {swap_total} MB ({swap_pct:.1f}%)")

    du = facts.get("disk_usage", {})
    if du:
        table.add_row("Disk (/)", f"{du.get('used', '?')} / {du.get('total', '?')} ({du.get('percent', '?')})")

    table.add_section()
    ds = facts.get("docker_summary", {})
    if ds.get("total", 0) > 0:
        table.add_row("Docker", f"{ds.get('running')} running / {ds.get('total')} total containers")
    else:
        table.add_row("Docker", "[dim]not running or no containers[/dim]")
        
    console.print(table)


def _resolve_vps_dir(vps_arg: Path) -> Path:
    """Resolve a VPS argument to a config directory.

    Accepts:
    - A directory path: config/vps/eu01.synercatalyst.com/
    - A VPS name: eu01.synercatalyst.com (searches config/vps/)
    """
    if vps_arg.is_dir():
        return vps_arg
    candidate = Path("config/vps") / str(vps_arg)
    if candidate.is_dir():
        return candidate
    console.print(f"[red]✗[/red] VPS directory not found: {vps_arg}")
    console.print(f"[dim]Searched: {vps_arg} (direct), {candidate} (config/vps/)[/dim]")
    raise typer.Exit(6)


def _load_vps_config(vps_dir: Path) -> dict[str, Any]:
    """Load and validate a VPS config from a directory's vps.yaml."""
    vps_yaml = vps_dir / "vps.yaml"
    if not vps_yaml.exists():
        console.print(f"[red]✗[/red] No vps.yaml found in {vps_dir}")
        raise typer.Exit(6)
    with vps_yaml.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        console.print(f"[red]✗[/red] Invalid config: expected mapping at top level")
        raise typer.Exit(6)
    if data.get("apiVersion") != "cstation/v1":
        console.print(f"[red]✗[/red] Unsupported apiVersion: {data.get('apiVersion')}")
        raise typer.Exit(6)
    if data.get("kind") != "VPS":
        console.print(f"[red]✗[/red] Unexpected kind: {data.get('kind')}")
        raise typer.Exit(6)
    return data


def _ssh_from_config(data: dict[str, Any]) -> SSHManager:
    """Build an SSHManager from a VPS config's access section."""
    access = data.get("access", {})
    host = access.get("host")
    if not host:
        console.print("[red]✗[/red] Config missing access.host")
        raise typer.Exit(6)
    return SSHManager(
        host=host,
        user=access.get("user", "root"),
        port=access.get("port", 22),
        key_filename=access.get("key"),
    )


def _apply_packages(ssh: SSHManager, baseline: dict[str, Any], pkg_mgr: str, *, dry_run: bool = False) -> list[str]:
    """Install missing packages. Returns list of packages installed/skipped."""
    desired = baseline.get("packages", [])
    if not desired:
        console.print("  [dim]packages: none specified[/dim]")
        return []

    installed_on_host = [p for p in desired if _package_installed(ssh, pkg_mgr, p)]
    missing = [p for p in desired if p not in installed_on_host]

    if not missing:
        console.print(f"  [green]✓[/green] packages: all {len(desired)} already installed")
        return []

    console.print(f"  [yellow]⟳[/yellow] packages: {', '.join(missing)} need installation")
    if dry_run:
        for p in missing:
            console.print(f"    [dim]would install: {p}[/dim]")
        return missing

    # Build install command based on package manager
    if pkg_mgr == "apt":
        cmd = f"apt-get update -qq && apt-get install -y -qq {' '.join(missing)}"
    elif pkg_mgr in ("dnf", "yum"):
        cmd = f"{pkg_mgr} install -y {' '.join(missing)}"
    elif pkg_mgr == "apk":
        cmd = f"apk add {' '.join(missing)}"
    else:
        console.print(f"  [red]✗[/red] packages: unsupported package manager '{pkg_mgr}'")
        return []

    result = ssh.run(cmd, sudo=True)
    if result and getattr(result, "exited", 0) == 0:
        console.print(f"  [green]✓[/green] packages: installed {', '.join(missing)}")
    else:
        stderr = getattr(result, "stderr", "") or ""
        console.print(f"  [red]✗[/red] packages: install failed{': ' + stderr.strip() if stderr else ''}")

    return missing


def _apply_upgrade_all(ssh: SSHManager, baseline: dict[str, Any], pkg_mgr: str, *, dry_run: bool = False) -> bool:
    if not baseline.get("upgrade_all"):
        console.print("  [dim]upgrade: not requested[/dim]")
        return False

    if pkg_mgr == "apt":
        cmd = "apt-get update -qq && apt-get upgrade -y -qq"
    elif pkg_mgr in ("dnf", "yum"):
        cmd = f"{pkg_mgr} upgrade -y"
    elif pkg_mgr == "apk":
        cmd = "apk update && apk upgrade"
    else:
        console.print(f"  [red]✗[/red] upgrade: unsupported package manager '{pkg_mgr}'")
        return False

    if dry_run:
        console.print(f"  [yellow]⟳[/yellow] upgrade: would upgrade all packages")
        return True

    result = ssh.run(cmd, sudo=True)
    if result and getattr(result, "exited", 0) == 0:
        console.print(f"  [green]✓[/green] upgrade: all packages upgraded")
        return True
    stderr = getattr(result, "stderr", "") or ""
    console.print(f"  [red]✗[/red] upgrade: failed{': ' + stderr.strip() if stderr else ''}")
    return False


def _apply_shell(ssh: SSHManager, baseline: dict[str, Any], *, dry_run: bool = False) -> bool:
    shell = baseline.get("shell")
    if not shell:
        console.print("  [dim]shell: not configured[/dim]")
        return False

    valid_shells = {"zsh": "/usr/bin/zsh", "bash": "/bin/bash", "fish": "/usr/bin/fish"}
    if shell not in valid_shells:
        console.print(f"  [red]✗[/red] shell: unsupported shell '{shell}'")
        return False

    target_path = valid_shells[shell]

    result = ssh.run(f"command -v {shell}", hide=True)
    if not result or not getattr(result, "stdout", "").strip():
        if dry_run:
            console.print(f"  [yellow]⟳[/yellow] shell: would install {shell}")
            console.print(f"  [yellow]⟳[/yellow] shell: would set default shell to {target_path}")
            return True
        install_result = ssh.run(f"apt-get install -y -qq {shell}", sudo=True)
        if not install_result or getattr(install_result, "exited", 0) != 0:
            console.print(f"  [red]✗[/red] shell: failed to install {shell}")
            return False
        console.print(f"  [green]✓[/green] shell: installed {shell}")
    else:
        if dry_run:
            console.print(f"  [green]✓[/green] shell: {shell} already installed")
        else:
            console.print(f"  [green]✓[/green] shell: {shell} already installed")

    access_user = None
    if dry_run:
        access_user = "root"
    else:
        access_user = "root"

    result = ssh.run(f"getent passwd {access_user}", hide=True)
    if result:
        last_field = (getattr(result, "stdout", "") or "").strip().split(":")[-1]
        if last_field == target_path:
            if dry_run:
                console.print(f"  [green]✓[/green] shell: {access_user} already uses {shell}")
            else:
                console.print(f"  [green]✓[/green] shell: {access_user} already uses {shell}")
            return True

    if dry_run:
        console.print(f"  [yellow]⟳[/yellow] shell: would set {access_user} default shell to {target_path}")
        return True

    ssh.run(f"usermod -s {target_path} {access_user}", sudo=True)
    console.print(f"  [green]✓[/green] shell: set {access_user} default shell to {target_path}")
    return True


def _apply_terminal(ssh: SSHManager, baseline: dict[str, Any], *, dry_run: bool = False) -> bool:
    terminal = baseline.get("terminal")
    if not terminal:
        console.print("  [dim]terminal: not configured[/dim]")
        return False

    result = ssh.run("cat /etc/environment", hide=True, sudo=False)
    current = getattr(result, "stdout", "") or ""

    for line in current.splitlines():
        if line.strip().startswith("TERM="):
            current_term = line.strip().split("=", 1)[1].strip('"').strip("'")
            if current_term == terminal:
                if dry_run:
                    console.print(f"  [green]✓[/green] terminal: TERM already set to {terminal}")
                else:
                    console.print(f"  [green]✓[/green] terminal: TERM already set to {terminal}")
                return True
            break

    if dry_run:
        console.print(f"  [yellow]⟳[/yellow] terminal: would set TERM={terminal} in /etc/environment")
        return True

    entry = f"TERM={terminal}"
    if current.strip():
        ssh.run(f'bash -c \'echo "{entry}" >> /etc/environment\'', hide=True)
    else:
        ssh.run(f'bash -c \'echo "{entry}" > /etc/environment\'', hide=True)
    console.print(f"  [green]✓[/green] terminal: set TERM={terminal} in /etc/environment")
    return True


def _apply_sshd(ssh: SSHManager, sshd_config: dict[str, Any], *, dry_run: bool = False) -> bool:
    """Configure SSH daemon. Returns True if changes were made."""
    changes: list[str] = []

    # Disable password authentication
    if sshd_config.get("disable_password_auth"):
        result = ssh.run("grep -c '^PasswordAuthentication no' /etc/ssh/sshd_config 2>/dev/null || true", sudo=True)
        already_set = result and getattr(result, "stdout", "").strip() not in ("", "0")
        if already_set:
            console.print("  [green]✓[/green] sshd: password auth already disabled")
        else:
            changes.append("disable password authentication")
            if dry_run:
                console.print("    [dim]would set PasswordAuthentication no in /etc/ssh/sshd_config[/dim]")
            else:
                ssh.run("sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config", sudo=True)
                # Also ensure it's not overridden in sshd_config.d
                ssh.run("mkdir -p /etc/ssh/sshd_config.d && echo 'PasswordAuthentication no' > /etc/ssh/sshd_config.d/disable-password.conf", sudo=True)
                ssh.run("systemctl reload sshd || systemctl reload ssh", sudo=True)
                console.print("  [green]✓[/green] sshd: password auth disabled, sshd reloaded")

    return len(changes) > 0


def _apply_firewall(ssh: SSHManager, fw_config: dict[str, Any], *, dry_run: bool = False) -> bool:
    """Configure firewall. Returns True if changes were made."""
    mode = fw_config.get("mode", "ufw")
    allow_rules = fw_config.get("allow", [])

    if mode != "ufw":
        console.print(f"  [yellow]![/yellow] firewall: mode '{mode}' not yet supported, skipping")
        return False

    # Check if ufw is active
    result = ssh.run("ufw status", sudo=True)
    status_output = getattr(result, "stdout", "") or ""
    is_active = "Status: active" in status_output

    changes = False

    if not is_active:
        console.print("  [yellow]⟳[/yellow] firewall: ufw is inactive")
        if dry_run:
            console.print("    [dim]would enable ufw with default deny[/dim]")
            return True
        # Ensure SSH is allowed before enabling (prevent lockout)
        ssh.run("ufw allow 22/tcp", sudo=True)
        for rule in allow_rules:
            if rule != "22/tcp":
                ssh.run(f"ufw allow {rule}", sudo=True)
        ssh.run("ufw --force enable", sudo=True)
        console.print("  [green]✓[/green] firewall: ufw enabled with default deny")
        changes = True
    else:
        # ufw is active, check rules
        missing_rules: list[str] = []
        for rule in allow_rules:
            # Check if rule exists (normalize port/proto format)
            check = ssh.run(f"ufw status | grep -c '{rule}'", sudo=True)
            count = _first_line(check)
            if not count or count == "0":
                missing_rules.append(rule)

        if missing_rules:
            console.print(f"  [yellow]⟳[/yellow] firewall: missing rules: {', '.join(missing_rules)}")
            if dry_run:
                for rule in missing_rules:
                    console.print(f"    [dim]would allow: {rule}[/dim]")
                return True
            for rule in missing_rules:
                ssh.run(f"ufw allow {rule}", sudo=True)
            console.print(f"  [green]✓[/green] firewall: added rules {', '.join(missing_rules)}")
            changes = True
        else:
            console.print(f"  [green]✓[/green] firewall: ufw active, all rules present")

    # Ensure default deny
    if not dry_run:
        result = ssh.run("ufw status verbose | grep 'Default:'", sudo=True)
        default_out = getattr(result, "stdout", "") or ""
        if "deny (incoming)" not in default_out.lower() and "deny" not in default_out.lower():
            ssh.run("ufw default deny incoming", sudo=True)
            ssh.run("ufw default allow outgoing", sudo=True)
            console.print("  [green]✓[/green] firewall: set default deny incoming")
            changes = True

    return changes


def _apply_swap(ssh: SSHManager, swap_config: dict[str, Any], *, dry_run: bool = False) -> bool:
    size_gb = swap_config.get("size_gb")
    if not size_gb:
        console.print("  [dim]swap: not configured[/dim]")
        return False

    result = ssh.run("swapon --show --noheadings 2>/dev/null", sudo=True)
    swap_active = bool(result and getattr(result, "stdout", "").strip())
    if swap_active:
        console.print("  [green]✓[/green] swap: already active")
        return False

    if dry_run:
        console.print(f"  [yellow]⟳[/yellow] swap: would create {size_gb}GB swap file")
        return True

    ssh.run(f"fallocate -l {size_gb}G /swapfile", sudo=True)
    ssh.run("chmod 600 /swapfile", sudo=True)
    ssh.run("mkswap /swapfile", sudo=True)
    ssh.run("swapon /swapfile", sudo=True)

    fstab_result = ssh.run("grep -c '/swapfile' /etc/fstab 2>/dev/null || true", sudo=True)
    fstab_has_entry = fstab_result and getattr(fstab_result, "stdout", "").strip() not in ("", "0")
    if not fstab_has_entry:
        ssh.run("bash -c 'echo \"/swapfile none swap sw 0 0\" >> /etc/fstab'", sudo=True)

    console.print(f"  [green]✓[/green] swap: created {size_gb}GB swap file and enabled")
    return True


def _apply_tuning(ssh: SSHManager, tuning_config: dict[str, Any], journald_config: dict[str, Any], *, dry_run: bool = False) -> bool:
    if not tuning_config and not journald_config:
        console.print("  [dim]tuning: not configured[/dim]")
        return False

    changes = False

    if tuning_config:
        CONF_PATH = "/etc/sysctl.d/99-cstation.conf"
        param_to_sysctl = {
            "vm_swappiness": "vm.swappiness",
            "vm_overcommit_memory": "vm.overcommit_memory",
            "net_ipv4_tcp_max_syn_backlog": "net.ipv4.tcp_max_syn_backlog",
            "fs_inotify_max_user_watches": "fs.inotify.max_user_watches",
            "net_ipv4_tcp_keepalive_time": "net.ipv4.tcp_keepalive_time",
        }

        needed: dict[str, Any] = {}
        for yaml_key, sysctl_key in param_to_sysctl.items():
            desired = tuning_config.get(yaml_key)
            if desired is None:
                continue
            current_result = ssh.run(f"sysctl -n {sysctl_key} 2>/dev/null", hide=True)
            current_val = getattr(current_result, "stdout", "").strip() if current_result else ""
            if current_val != str(desired):
                needed[sysctl_key] = desired

        if not needed:
            console.print("  [green]✓[/green] tuning: all sysctl params already set")
        else:
            for key, val in needed.items():
                if dry_run:
                    console.print(f"  [yellow]⟳[/yellow] tuning: would set {key}={val}")
                else:
                    console.print(f"  [yellow]⟳[/yellow] tuning: setting {key}={val}")
            if not dry_run:
                lines = [f"{k} = {v}" for k, v in needed.items()]
                conf_content = "\n".join(lines) + "\n"
                ssh.run(f"bash -c 'cat > {CONF_PATH} << \"CSYSCTL\"\n{conf_content}CSYSCTL'", sudo=True)
                ssh.run("sysctl --system", sudo=True, hide=True)
                console.print("  [green]✓[/green] tuning: sysctl params applied")
            changes = True

    if journald_config:
        JOURNALD_DIR = "/etc/systemd/journald.conf.d"
        JOURNALD_PATH = f"{JOURNALD_DIR}/99-cstation.conf"
        current_result = ssh.run(f"cat {JOURNALD_PATH} 2>/dev/null", hide=True, sudo=True)
        current_content = getattr(current_result, "stdout", "").strip() if current_result else ""

        desired_lines: list[str] = ["[Journal]"]
        max_use = journald_config.get("system_max_use")
        if max_use:
            desired_lines.append(f"SystemMaxUse={max_use}")
        fwd = journald_config.get("forward_to_syslog")
        if fwd is not None:
            desired_lines.append(f"ForwardToSyslog={'yes' if fwd else 'no'}")
        desired_content = "\n".join(desired_lines)

        if current_content == desired_content:
            console.print("  [green]✓[/green] tuning: journald already configured")
        else:
            if dry_run:
                console.print(f"  [yellow]⟳[/yellow] tuning: would write {JOURNALD_PATH}")
            else:
                ssh.run(f"mkdir -p {JOURNALD_DIR}", sudo=True)
                ssh.run(f"bash -c 'cat > {JOURNALD_PATH} << \"CJOURNAL\"\n{desired_content}\nCJOURNAL'", sudo=True)
                ssh.run("systemctl restart systemd-journald", sudo=True)
                console.print(f"  [green]✓[/green] tuning: journald configured and restarted")
            changes = True

    return changes


def _apply_fail2ban(ssh: SSHManager, f2b_config: dict[str, Any], *, dry_run: bool = False) -> bool:
    if not f2b_config:
        console.print("  [dim]fail2ban: not configured[/dim]")
        return False

    JAIL_PATH = "/etc/fail2ban/jail.local"
    bantime = f2b_config.get("bantime", "10m")
    findtime = f2b_config.get("findtime", "10m")
    maxretry = f2b_config.get("maxretry", 5)

    desired_content = (
        f"[DEFAULT]\n"
        f"bantime = {bantime}\n"
        f"findtime = {findtime}\n"
        f"maxretry = {maxretry}\n"
        f"banaction = nftables\n"
        f"backend = systemd\n\n"
        f"[sshd]\n"
        f"enabled = true\n"
    )

    current_result = ssh.run(f"cat {JAIL_PATH} 2>/dev/null", hide=True, sudo=True)
    current_content = getattr(current_result, "stdout", "") if current_result else ""

    if current_content.strip() == desired_content.strip():
        console.print("  [green]✓[/green] fail2ban: jail.local already configured")
        return False

    if dry_run:
        console.print(f"  [yellow]⟳[/yellow] fail2ban: would write {JAIL_PATH}")
        console.print(f"    [dim]bantime={bantime}, findtime={findtime}, maxretry={maxretry}[/dim]")
        return True

    ssh.run(f"bash -c 'cat > {JAIL_PATH} << \"CF2B\"\n{desired_content}CF2B'", sudo=True)
    ssh.run("systemctl restart fail2ban", sudo=True)
    console.print(f"  [green]✓[/green] fail2ban: jail.local written and restarted")
    return True


def _apply_hostname(ssh: SSHManager, hostname: Optional[str], *, dry_run: bool = False) -> bool:
    if not hostname:
        console.print("  [dim]hostname: not configured[/dim]")
        return False

    current_result = ssh.run("hostname", hide=True)
    current = getattr(current_result, "stdout", "").strip() if current_result else ""

    if current == hostname:
        console.print(f"  [green]✓[/green] hostname: already set to {hostname}")
        return False

    if dry_run:
        console.print(f"  [yellow]⟳[/yellow] hostname: would set to {hostname} (currently {current})")
        return True

    ssh.run(f"hostnamectl set-hostname {hostname}", sudo=True)
    console.print(f"  [green]✓[/green] hostname: set to {hostname}")
    return True


def _apply_docker_daemon(ssh: SSHManager, daemon_config: dict[str, Any], *, dry_run: bool = False) -> bool:
    if not daemon_config:
        console.print("  [dim]docker_daemon: not configured[/dim]")
        return False

    DAEMON_JSON_PATH = "/etc/docker/daemon.json"
    current_result = ssh.run(f"cat {DAEMON_JSON_PATH} 2>/dev/null", hide=True, sudo=True)
    current_content = getattr(current_result, "stdout", "").strip() if current_result else ""

    desired_json = {}
    log_driver = daemon_config.get("log_driver")
    if log_driver:
        desired_json["log-driver"] = log_driver
    log_opts = daemon_config.get("log_opts", {})
    if log_opts:
        desired_json["log-opts"] = {k.replace("_", "-"): v for k, v in log_opts.items()}
    storage_driver = daemon_config.get("storage_driver")
    if storage_driver:
        desired_json["storage-driver"] = storage_driver
    if daemon_config.get("live_restore") is not None:
        desired_json["live-restore"] = daemon_config["live_restore"]
    if daemon_config.get("iptables") is not None:
        desired_json["iptables"] = daemon_config["iptables"]
    ulimits = daemon_config.get("default_ulimits", {})
    if ulimits:
        desired_json["default-ulimits"] = {name: {"hard": val, "soft": val} for name, val in ulimits.items()}

    desired_content = jsonlib.dumps(desired_json, indent=2)

    if current_content == desired_content:
        console.print("  [green]✓[/green] docker_daemon: daemon.json already configured")
        return False

    if dry_run:
        console.print(f"  [yellow]⟳[/yellow] docker_daemon: would write {DAEMON_JSON_PATH}")
        for key in desired_json:
            console.print(f"    [dim]{key}: {desired_json[key]}[/dim]")
        return True

    ssh.run(f"mkdir -p /etc/docker", sudo=True)
    ssh.run(f"bash -c 'cat > {DAEMON_JSON_PATH} << \"CDAEMON\"\n{desired_content}\nCDAEMON'", sudo=True)
    ssh.run("systemctl restart docker", sudo=True)
    console.print(f"  [green]✓[/green] docker_daemon: daemon.json written and docker restarted")
    return True


def _apply_docker_networks(ssh: SSHManager, networks: list[str], *, dry_run: bool = False) -> bool:
    if not networks:
        console.print("  [dim]docker_networks: none configured[/dim]")
        return False

    result = ssh.run("docker network ls --format '{{.Name}}'", hide=True)
    existing = set()
    if result and getattr(result, "stdout", "").strip():
        existing = {line.strip() for line in result.stdout.strip().splitlines() if line.strip()}

    missing = [n for n in networks if n not in existing]

    if not missing:
        console.print(f"  [green]✓[/green] docker_networks: all networks exist ({', '.join(networks)})")
        return False

    if dry_run:
        for n in missing:
            console.print(f"  [yellow]⟳[/yellow] docker_networks: would create network {n}")
        return True

    for n in missing:
        ssh.run(f"docker network create {n}", sudo=True)
        console.print(f"  [green]✓[/green] docker_networks: created network {n}")
    return True


def _apply_docker_directories(ssh: SSHManager, directories: list[str], *, dry_run: bool = False) -> bool:
    if not directories:
        console.print("  [dim]docker_directories: none configured[/dim]")
        return False

    missing = []
    for d in directories:
        result = ssh.run(f"test -d {d} && echo exists || echo missing", hide=True)
        status = getattr(result, "stdout", "").strip() if result else "missing"
        if status != "exists":
            missing.append(d)

    if not missing:
        console.print(f"  [green]✓[/green] docker_directories: all directories exist")
        return False

    if dry_run:
        for d in missing:
            console.print(f"  [yellow]⟳[/yellow] docker_directories: would create {d}")
        return True

    for d in missing:
        ssh.run(f"mkdir -p {d}", sudo=True)
        console.print(f"  [green]✓[/green] docker_directories: created {d}")
    return True


@vps_app.command("plan")
def vps_plan(
    vps: str = typer.Argument(..., help="VPS name or directory path (e.g. eu01.synercatalyst.com or config/vps/eu01.synercatalyst.com)"),
) -> None:
    """
    Dry-run: show what would be applied to the VPS without making changes.

    Reads the VPS config and compares declared state against actual state,
    printing a summary of actions that `apply` would perform.
    """
    vps_dir = _resolve_vps_dir(Path(vps))
    data = _load_vps_config(vps_dir)
    identity = data.get("identity", {})
    name = identity.get("name", vps_dir.name)
    console.print(f"\n[bold]VPS Plan: {name}[/bold] [dim]({vps_dir}/vps.yaml)[/dim]\n")

    ssh = _ssh_from_config(data)
    baseline = data.get("os", {}).get("baseline", {})
    docker_config = data.get("docker", {})

    # Detect package manager from facts
    pkg_mgr = data.get("facts", {}).get("os", {}).get("package_manager")
    if not pkg_mgr:
        os_id = data.get("facts", {}).get("os", {}).get("id", "")
        pkg_mgr = _detect_package_manager(ssh, os_id)

    console.print("[bold]Phase 1: Upgrade All Packages[/bold]")
    _apply_upgrade_all(ssh, baseline, pkg_mgr, dry_run=True)

    console.print("\n[bold]Phase 2: Packages[/bold]")
    _apply_packages(ssh, baseline, pkg_mgr, dry_run=True)

    console.print("\n[bold]Phase 3: Shell[/bold]")
    _apply_shell(ssh, baseline, dry_run=True)

    console.print("\n[bold]Phase 4: Terminal[/bold]")
    _apply_terminal(ssh, baseline, dry_run=True)

    console.print("\n[bold]Phase 5: SSH Daemon[/bold]")
    sshd_cfg = baseline.get("sshd", {})
    if not sshd_cfg:
        console.print("  [dim]sshd: no configuration specified[/dim]")
    else:
        _apply_sshd(ssh, sshd_cfg, dry_run=True)

    console.print("\n[bold]Phase 6: Firewall[/bold]")
    fw_cfg = baseline.get("firewall", {})
    if not fw_cfg:
        console.print("  [dim]firewall: no configuration specified[/dim]")
    else:
        _apply_firewall(ssh, fw_cfg, dry_run=True)

    console.print("\n[bold]Phase 7: Swap[/bold]")
    _apply_swap(ssh, baseline.get("swap", {}), dry_run=True)

    console.print("\n[bold]Phase 8: Kernel Tuning + Journald[/bold]")
    _apply_tuning(ssh, baseline.get("tuning", {}), data.get("os", {}).get("journald", {}), dry_run=True)

    console.print("\n[bold]Phase 9: Fail2Ban[/bold]")
    _apply_fail2ban(ssh, baseline.get("fail2ban", {}), dry_run=True)

    console.print("\n[bold]Phase 10: Hostname[/bold]")
    _apply_hostname(ssh, data.get("os", {}).get("hostname"), dry_run=True)

    console.print("\n[bold]Phase 11: Docker Daemon[/bold]")
    _apply_docker_daemon(ssh, docker_config.get("daemon", {}), dry_run=True)

    console.print("\n[bold]Phase 12: Docker Networks[/bold]")
    _apply_docker_networks(ssh, docker_config.get("networks", []), dry_run=True)

    console.print("\n[bold]Phase 13: Docker Directories[/bold]")
    _apply_docker_directories(ssh, docker_config.get("directories", []), dry_run=True)

    console.print("\n[dim]Run 'cstation vps apply <vps>' to execute these changes.[/dim]")


@vps_app.command("apply")
def vps_apply(
    vps: str = typer.Argument(..., help="VPS name or directory path (e.g. eu01.synercatalyst.com or config/vps/eu01.synercatalyst.com)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    phase: Optional[str] = typer.Option(None, "--phase", help="Run only a specific phase: upgrade_all, packages, shell, terminal, sshd, firewall, swap, tuning, fail2ban, hostname, docker_daemon, docker_networks, docker_directories"),
) -> None:
    """
    Apply VPS configuration: install packages, configure sshd, configure firewall, set up swap, tuning, Docker.

    Reads the VPS config and applies the os.baseline, os, and docker sections, making the
    actual server match the declared state. Use 'plan' first to preview changes.

    Examples:
      cstation vps plan eu01.synercatalyst.com
      cstation vps apply eu01.synercatalyst.com
      cstation vps apply eu01.synercatalyst.com --phase packages
      cstation vps apply eu01.synercatalyst.com --phase docker_daemon
    """
    vps_dir = _resolve_vps_dir(Path(vps))
    data = _load_vps_config(vps_dir)
    identity = data.get("identity", {})
    name = identity.get("name", vps_dir.name)
    console.print(f"\n[bold]VPS Apply: {name}[/bold] [dim]({vps_dir}/vps.yaml)[/dim]\n")

    ssh = _ssh_from_config(data)
    baseline = data.get("os", {}).get("baseline", {})
    docker_config = data.get("docker", {})

    # Detect package manager from facts
    pkg_mgr = data.get("facts", {}).get("os", {}).get("package_manager")
    if not pkg_mgr:
        os_id = data.get("facts", {}).get("os", {}).get("id", "")
        pkg_mgr = _detect_package_manager(ssh, os_id)

    # Confirmation
    if not yes:
        console.print("[yellow]⚠[/yellow] This will modify the remote server. Changes:")
        phases_to_run = []
        if phase is None or phase == "upgrade_all":
            if baseline.get("upgrade_all"):
                phases_to_run.append("  upgrade_all: upgrade all installed packages")
        if phase is None or phase == "packages":
            pkgs = baseline.get("packages", [])
            if pkgs:
                phases_to_run.append(f"  packages: install {', '.join(pkgs)} (if missing)")
        if phase is None or phase == "shell":
            shell = baseline.get("shell")
            if shell:
                phases_to_run.append(f"  shell: set default shell to {shell}")
        if phase is None or phase == "terminal":
            terminal = baseline.get("terminal")
            if terminal:
                phases_to_run.append(f"  terminal: set TERM={terminal} in /etc/environment")
        if phase is None or phase == "sshd":
            sshd_cfg = baseline.get("sshd", {})
            if sshd_cfg.get("disable_password_auth"):
                phases_to_run.append("  sshd: disable password authentication")
        if phase is None or phase == "firewall":
            fw_cfg = baseline.get("firewall", {})
            if fw_cfg:
                phases_to_run.append(f"  firewall: configure {fw_cfg.get('mode', 'ufw')}, allow {fw_cfg.get('allow', [])}")
        if phase is None or phase == "swap":
            swap_cfg = baseline.get("swap", {})
            if swap_cfg.get("size_gb"):
                phases_to_run.append(f"  swap: create {swap_cfg['size_gb']}GB swap file")
        if phase is None or phase == "tuning":
            tuning_cfg = baseline.get("tuning", {})
            journald_cfg = data.get("os", {}).get("journald", {})
            if tuning_cfg or journald_cfg:
                phases_to_run.append("  tuning: configure kernel sysctl + journald")
        if phase is None or phase == "fail2ban":
            f2b_cfg = baseline.get("fail2ban", {})
            if f2b_cfg:
                phases_to_run.append("  fail2ban: configure jail.local")
        if phase is None or phase == "hostname":
            hostname_cfg = data.get("os", {}).get("hostname")
            if hostname_cfg:
                phases_to_run.append(f"  hostname: set to {hostname_cfg}")
        if phase is None or phase == "docker_daemon":
            daemon_cfg = docker_config.get("daemon", {})
            if daemon_cfg:
                phases_to_run.append("  docker_daemon: configure /etc/docker/daemon.json")
        if phase is None or phase == "docker_networks":
            nets = docker_config.get("networks", [])
            if nets:
                phases_to_run.append(f"  docker_networks: create {', '.join(nets)}")
        if phase is None or phase == "docker_directories":
            dirs = docker_config.get("directories", [])
            if dirs:
                phases_to_run.append(f"  docker_directories: create {', '.join(dirs)}")

        if not phases_to_run:
            console.print("[dim]No changes to apply.[/dim]")
            raise typer.Exit(0)

        for line in phases_to_run:
            console.print(line)

        confirm = typer.confirm("\nProceed?", default=False)
        if not confirm:
            console.print("[dim]Aborted.[/dim]")
            raise typer.Exit(0)
        console.print()

    # Phase 1: Upgrade All Packages
    if phase is None or phase == "upgrade_all":
        console.print("[bold]Phase 1: Upgrade All Packages[/bold]")
        _apply_upgrade_all(ssh, baseline, pkg_mgr, dry_run=False)
        console.print()

    # Phase 2: Packages
    if phase is None or phase == "packages":
        console.print("[bold]Phase 2: Packages[/bold]")
        _apply_packages(ssh, baseline, pkg_mgr, dry_run=False)
        console.print()

    # Phase 3: Shell
    if phase is None or phase == "shell":
        console.print("[bold]Phase 3: Shell[/bold]")
        _apply_shell(ssh, baseline, dry_run=False)
        console.print()

    # Phase 4: Terminal
    if phase is None or phase == "terminal":
        console.print("[bold]Phase 4: Terminal[/bold]")
        _apply_terminal(ssh, baseline, dry_run=False)
        console.print()

    # Phase 5: SSH Daemon
    if phase is None or phase == "sshd":
        console.print("[bold]Phase 5: SSH Daemon[/bold]")
        sshd_cfg = baseline.get("sshd", {})
        if not sshd_cfg:
            console.print("  [dim]sshd: no configuration specified[/dim]")
        else:
            _apply_sshd(ssh, sshd_cfg, dry_run=False)
        console.print()

    # Phase 6: Firewall
    if phase is None or phase == "firewall":
        console.print("[bold]Phase 6: Firewall[/bold]")
        fw_cfg = baseline.get("firewall", {})
        if not fw_cfg:
            console.print("  [dim]firewall: no configuration specified[/dim]")
        else:
            _apply_firewall(ssh, fw_cfg, dry_run=False)
        console.print()

    # Phase 7: Swap
    if phase is None or phase == "swap":
        console.print("[bold]Phase 7: Swap[/bold]")
        _apply_swap(ssh, baseline.get("swap", {}), dry_run=False)
        console.print()

    # Phase 8: Kernel Tuning + Journald
    if phase is None or phase == "tuning":
        console.print("[bold]Phase 8: Kernel Tuning + Journald[/bold]")
        _apply_tuning(ssh, baseline.get("tuning", {}), data.get("os", {}).get("journald", {}), dry_run=False)
        console.print()

    # Phase 9: Fail2Ban
    if phase is None or phase == "fail2ban":
        console.print("[bold]Phase 9: Fail2Ban[/bold]")
        _apply_fail2ban(ssh, baseline.get("fail2ban", {}), dry_run=False)
        console.print()

    # Phase 10: Hostname
    if phase is None or phase == "hostname":
        console.print("[bold]Phase 10: Hostname[/bold]")
        _apply_hostname(ssh, data.get("os", {}).get("hostname"), dry_run=False)
        console.print()

    # Phase 11: Docker Daemon
    if phase is None or phase == "docker_daemon":
        console.print("[bold]Phase 11: Docker Daemon[/bold]")
        _apply_docker_daemon(ssh, docker_config.get("daemon", {}), dry_run=False)
        console.print()

    # Phase 12: Docker Networks
    if phase is None or phase == "docker_networks":
        console.print("[bold]Phase 12: Docker Networks[/bold]")
        _apply_docker_networks(ssh, docker_config.get("networks", []), dry_run=False)
        console.print()

    # Phase 13: Docker Directories
    if phase is None or phase == "docker_directories":
        console.print("[bold]Phase 13: Docker Directories[/bold]")
        _apply_docker_directories(ssh, docker_config.get("directories", []), dry_run=False)
        console.print()

    console.print(f"[green]✓[/green] Apply complete for [bold]{name}[/bold]")


def _pick_best_ip(facts: dict[str, Any], fallback: str) -> str:
    """Try to find a public IPv4 from facts, falling back to the provided string."""
    interfaces = facts.get("network", {}).get("interfaces", [])
    
    # Priority 1: A non-internal, UP IPv4
    for iface in interfaces:
        ip = iface.get("ipv4")
        if not ip or iface.get("state") != "UP":
            continue
        # Skip local/private/docker ranges
        if ip.startswith(("127.", "172.", "10.", "192.168.")):
            continue
        return ip
        
    # Priority 2: Any UP IPv4 that isn't loopback
    for iface in interfaces:
        ip = iface.get("ipv4")
        if ip and iface.get("state") == "UP" and not ip.startswith("127."):
            return ip
            
    return fallback


@vps_app.command("init")
def vps_init(
    target: str = typer.Argument(..., help="Target hostname/IP (e.g. sg01.com) or <provider>/<account>:<id>"),
    stage: str = typer.Option("prod", "--stage"),
    out: Optional[Path] = typer.Option(None, "--out", help="Output YAML path"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing output"),
    user: str = typer.Option("root", "--user"),
    port: int = typer.Option(22, "--port"),
    key: Optional[Path] = typer.Option(None, "--key", help="SSH private key"),
) -> None:
    """
    Initialize a per-VPS config from provider metadata + SSH facts.

    For servers with SSH access, simply provide the hostname or IP.
    For cloud providers, use <provider>/<account>:<id>.

    Examples:
      cstation vps init sg01.synercatalyst.com --port 8288
      cstation vps init 1.2.3.4
      cstation vps init hetzner/ANSIS:123456
    """
    if "/" not in target:
        # If no provider/ prefix is given, assume static provider
        provider_name = "static"
        account_name = "manual"
        id_, name = None, target
    else:
        provider_name, rest = target.split("/", 1)
        account_name, raw_target = _split_account_target(rest)
        if account_name is None:
            raise typer.BadParameter("Target must include account: <provider>/<account>:<id>")
        id_, name = _parse_target(raw_target)
        if not id_ and not name:
            raise typer.BadParameter("Target must include VPS id or name after <account>:")

    output_path = out
    if output_path is not None and output_path.exists() and not force:
        console.print(f"[red]✗[/red] Output path already exists: {output_path}")
        raise typer.Exit(5)

    try:
        _, provider = _provider(provider_name, account_name)
        vps = provider.get_vps(id=id_, name=name)
    except ProviderNotFoundError as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(3)
    except ProviderAuthError as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(2)
    except ProviderError as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(1)

    resolved_name = vps.name
    resolved_region = vps.region or "unknown"
    output_path = output_path or Path("config") / "vps" / resolved_name / "vps.yaml"

    if output_path.exists() and not force:
        console.print(f"[red]✗[/red] Output file already exists: {output_path}")
        raise typer.Exit(5)

    host = vps.ipv4 or vps.ipv6
    if not host:
        console.print("[red]✗[/red] VPS has no reachable IP address")
        raise typer.Exit(4)

    ssh = SSHManager(host=host, user=user, key_filename=str(key) if key else None, port=port)
    facts = _collect_facts(ssh)

    # Use the discovered public IP if we used a hostname for static provider
    if provider_name == "static":
        real_ip = _pick_best_ip(facts, host)
        if real_ip != host:
            console.print(f"  [dim]Discovered real IP: {real_ip}[/dim]")
            host = real_ip

    # Build access dict, omitting null key
    access: dict[str, Any] = {
        "host": host,
        "user": user,
        "port": port,
    }
    if key:
        access["key"] = str(key)

    # os.baseline: suggest missing packages for install
    missing_packages = facts.get("packages", {}).get("missing", [])
    baseline_packages = [p for p in missing_packages if p in ("fail2ban", "docker.io", "containerd", "ufw", "nftables")]

    payload = {
        "apiVersion": "cstation/v1",
        "kind": "VPS",
        "identity": {
            "name": resolved_name,
            "stage": stage,
            "region": resolved_region,
            "provider": provider_name,
        },
        "access": access,
        "facts": facts,
        "os": {
            "baseline": {
                "packages": baseline_packages,
                "sshd": {"disable_password_auth": True},
                "firewall": {"mode": "ufw", "allow": ["22/tcp"]},
            }
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    clean_payload = _strip_nulls(payload)
    
    # Overwrite if force or file doesn't exist (the existence check was done earlier)
    with output_path.open("w", encoding="utf-8") as f:
        yaml.dump(clean_payload, f, sort_keys=False, Dumper=_CStationYamlDumper)

    console.print(f"[green]✓[/green] Wrote {output_path}")


def _check_running_containers(ssh: SSHManager) -> list[str] | None:
    try:
        result = ssh.run("docker ps --format '{{.Names}}'", sudo=True)
        if result is None:
            return None
        output = result.stdout.strip()
        if not output:
            return []
        return [name for name in output.splitlines() if name.strip()]
    except Exception:
        return None


def _remove_vps_secrets(vps_name: str) -> bool:
    config_path = Path.home() / ".config" / "cstation" / "config.yaml"
    if not config_path.exists():
        return False
    try:
        with config_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        return False
    secrets = data.get("vps", {}).get("secrets", {})
    if vps_name not in secrets:
        return False
    del secrets[vps_name]
    if not secrets:
        data.setdefault("vps", {}).pop("secrets", None)
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with config_path.open("w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, Dumper=_CStationYamlDumper)
        return True
    except Exception:
        return False


@vps_app.command("remove")
def vps_remove(
    vps: str = typer.Argument(..., help="VPS name or directory path"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    skip_check: bool = typer.Option(False, "--skip-check", help="Skip SSH container check (use if server is unreachable)"),
) -> None:
    """
    Remove a VPS from local configuration: remove its config directory and secrets.

    This does NOT destroy the VPS on the cloud provider. To remove the server itself,
    use the provider's web console or API directly.

    Examples:
      cstation vps remove eu01.synercatalyst.com
      cstation vps remove config/vps/eu01.synercatalyst.com --yes
      cstation vps remove eu01.synercatalyst.com --skip-check
    """
    vps_dir = _resolve_vps_dir(Path(vps))
    data = _load_vps_config(vps_dir)
    identity = data.get("identity", {})
    name = identity.get("name", vps_dir.name)

    console.print(f"\n[bold]VPS Remove: {name}[/bold]\n")

    containers_warning = None
    if skip_check:
        console.print("[dim]  Skipping container check (--skip-check).[/dim]")
    else:
        try:
            ssh = _ssh_from_config(data)
            ssh.connection.open_timeout = 10
            containers = _check_running_containers(ssh)
            if containers is None:
                console.print("[dim]  Could not check running containers (SSH unavailable).[/dim]")
            elif containers:
                console.print(f"[yellow]⚠ Running containers detected: {', '.join(containers)}[/yellow]")
                containers_warning = containers
            else:
                console.print("[dim]  No running containers detected.[/dim]")
        except Exception:
            console.print("[dim]  Could not check running containers (SSH connection failed).[/dim]")
            console.print("[dim]  Use --skip-check if the server is already unreachable.[/dim]")

    files_in_dir = list(vps_dir.iterdir()) if vps_dir.is_dir() else []
    console.print(f"\n[red]This will permanently delete:[/red]")
    console.print(f"  Config directory: {vps_dir}/")
    for f in sorted(files_in_dir):
        console.print(f"    {f.name}")
    console.print(f"  Secrets: vps.secrets.{name} from ~/.config/cstation/config.yaml")

    if containers_warning:
        console.print(f"\n[yellow]⚠ {len(containers_warning)} container(s) are still running on {name}.[/yellow]")
        console.print("[yellow]Consider stopping them before removing, or use the provider console to destroy the VPS.[/yellow]")

    if not yes:
        confirm = typer.confirm("\nProceed with removal?", default=False)
        if not confirm:
            console.print("[dim]Aborted.[/dim]")
            raise typer.Exit(0)

    shutil.rmtree(vps_dir)
    console.print(f"  [green]✓[/green] Deleted {vps_dir}/")

    secrets_removed = _remove_vps_secrets(name)
    if secrets_removed:
        config_path = Path.home() / ".config" / "cstation" / "config.yaml"
        console.print(f"  [green]✓[/green] Removed secrets from {config_path}")
    else:
        console.print(f"  [dim]No secrets found for {name} in config.yaml[/dim]")

    console.print(f"\n[green]✓[/green] Removed VPS [bold]{name}[/bold]")


@vps_app.callback()
def vps_callback(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        rprint(ctx.get_help())
        raise typer.Exit(0)
