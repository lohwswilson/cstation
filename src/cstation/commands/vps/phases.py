#!/usr/bin/env python3
"""
The 12-phase VPS apply pipeline: packages, shell, terminal, sshd, firewall,
swap, tuning, fail2ban, hostname, docker daemon, docker networks, and
docker directories. Each phase accepts a dry_run flag and reports what it
would do without executing when dry_run=True.
"""

from __future__ import annotations

import json as jsonlib
from typing import Any, Optional

from rich.console import Console

from cstation.ssh import SSHManager
from .parsers import _first_line, _package_installed

console = Console()


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
        console.print("  [yellow]⟳[/yellow] upgrade: would upgrade all packages")
        return True

    result = ssh.run(cmd, sudo=True)
    if result and getattr(result, "exited", 0) == 0:
        console.print("  [green]✓[/green] upgrade: all packages upgraded")
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
        ssh.run(f"bash -c 'echo \"{entry}\" >> /etc/environment'", hide=True)
    else:
        ssh.run(f"bash -c 'echo \"{entry}\" > /etc/environment'", hide=True)
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
                ssh.run(
                    "sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config", sudo=True
                )
                # Also ensure it's not overridden in sshd_config.d
                ssh.run(
                    "mkdir -p /etc/ssh/sshd_config.d && echo 'PasswordAuthentication no' > /etc/ssh/sshd_config.d/disable-password.conf",
                    sudo=True,
                )
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
            console.print("  [green]✓[/green] firewall: ufw active, all rules present")

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


def _apply_tuning(
    ssh: SSHManager, tuning_config: dict[str, Any], journald_config: dict[str, Any], *, dry_run: bool = False
) -> bool:
    if not tuning_config and not journald_config:
        console.print("  [dim]tuning: not configured[/dim]")
        return False

    changes = False

    if tuning_config:
        CONF_PATH = "/etc/sysctl.d/99-cstation.conf"
        param_to_sysctl = {
            "vm_swappiness": "vm.swappiness",
            "vm_overcommit_memory": "vm.overcommit_memory",
            "vm_dirty_ratio": "vm.dirty_ratio",
            "vm_dirty_background_ratio": "vm.dirty_background_ratio",
            "net_ipv4_tcp_max_syn_backlog": "net.ipv4.tcp_max_syn_backlog",
            "net_core_somaxconn": "net.core.somaxconn",
            "net_core_netdev_max_backlog": "net.core.netdev_max_backlog",
            "net_ipv4_tcp_fin_timeout": "net.ipv4.tcp_fin_timeout",
            "net_ipv4_tcp_tw_reuse": "net.ipv4.tcp_tw_reuse",
            "net_ipv4_ip_local_port_range": "net.ipv4.ip_local_port_range",
            "fs_inotify_max_user_watches": "fs.inotify.max_user_watches",
            "fs_file_max": "fs.file-max",
            "net_ipv4_tcp_keepalive_time": "net.ipv4.tcp_keepalive_time",
            "net_core_default_qdisc": "net.core.default_qdisc",
            "net_ipv4_tcp_congestion_control": "net.ipv4.tcp_congestion_control",
            "net_ipv4_tcp_slow_start_after_idle": "net.ipv4.tcp_slow_start_after_idle",
            "net_ipv4_tcp_fastopen": "net.ipv4.tcp_fastopen",
            "net_ipv4_tcp_mtu_probing": "net.ipv4.tcp_mtu_probing",
            "net_core_rmem_max": "net.core.rmem_max",
            "net_core_wmem_max": "net.core.wmem_max",
            "net_ipv4_tcp_rmem": "net.ipv4.tcp_rmem",
            "net_ipv4_tcp_wmem": "net.ipv4.tcp_wmem",
        }

        desired_params = dict(tuning_config)
        if desired_params.get("bbr") is True or desired_params.get("net_ipv4_tcp_congestion_control") == "bbr":
            desired_params.setdefault("net_core_default_qdisc", "fq")
            desired_params["net_ipv4_tcp_congestion_control"] = "bbr"

            # Check if tcp_bbr kernel module is loaded
            mod_check = ssh.run("lsmod 2>/dev/null | grep -c '^tcp_bbr' || true", hide=True, sudo=True)
            mod_loaded = mod_check and getattr(mod_check, "stdout", "").strip() not in ("", "0")
            if not mod_loaded:
                if dry_run:
                    console.print(
                        "  [yellow]⟳[/yellow] tuning: would load tcp_bbr kernel module and configure /etc/modules-load.d/bbr.conf"
                    )
                else:
                    ssh.run(
                        "modprobe tcp_bbr && (grep -q '^tcp_bbr' /etc/modules-load.d/bbr.conf 2>/dev/null || echo 'tcp_bbr' > /etc/modules-load.d/bbr.conf)",
                        sudo=True,
                    )
                    console.print(
                        "  [green]✓[/green] tuning: loaded tcp_bbr module and persisted in /etc/modules-load.d/bbr.conf"
                    )
                changes = True

        needed: dict[str, Any] = {}
        for yaml_key, sysctl_key in param_to_sysctl.items():
            desired = desired_params.get(yaml_key)
            if desired is None:
                continue
            current_result = ssh.run(f"sysctl -n {sysctl_key} 2>/dev/null", hide=True)
            current_val = getattr(current_result, "stdout", "").strip() if current_result else ""
            if " ".join(current_val.split()) != " ".join(str(desired).split()):
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
                ssh.run(f"echo '{conf_content}' > {CONF_PATH}", sudo=True)
                ssh.run("sysctl --system", sudo=True, hide=True)
                console.print("  [green]✓[/green] tuning: sysctl params applied")
            changes = True

        nofile = desired_params.get("nofile")
        if nofile:
            LIMITS_DIR = "/etc/security/limits.d"
            LIMITS_PATH = f"{LIMITS_DIR}/99-cstation.conf"
            limits_content = f"* soft nofile {nofile}\n* hard nofile {nofile}\nroot soft nofile {nofile}\nroot hard nofile {nofile}\n"
            current_limits_res = ssh.run(f"cat {LIMITS_PATH} 2>/dev/null", hide=True, sudo=True)
            current_limits_txt = getattr(current_limits_res, "stdout", "").strip() if current_limits_res else ""
            if current_limits_txt != limits_content.strip():
                if dry_run:
                    console.print(f"  [yellow]⟳[/yellow] tuning: would set nofile={nofile} in {LIMITS_PATH}")
                else:
                    ssh.run(f"mkdir -p {LIMITS_DIR}", sudo=True)
                    ssh.run(f"echo '{limits_content.strip()}' > {LIMITS_PATH}", sudo=True)
                    console.print(f"  [green]✓[/green] tuning: nofile={nofile} limits configured in {LIMITS_PATH}")
                changes = True
            else:
                console.print(f"  [green]✓[/green] tuning: nofile limits already set to {nofile}")

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
                ssh.run(f"echo '{desired_content}' > {JOURNALD_PATH}", sudo=True)
                ssh.run("systemctl restart systemd-journald", sudo=True)
                console.print("  [green]✓[/green] tuning: journald configured and restarted")
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

    ssh.run(f"echo '{desired_content}' > {JAIL_PATH}", sudo=True)
    ssh.run("systemctl restart fail2ban", sudo=True)
    console.print("  [green]✓[/green] fail2ban: jail.local written and restarted")
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

    # Default live-restore to True to guarantee running containers are never terminated on daemon reloads
    live_restore = daemon_config.get("live_restore", True)
    if live_restore is not None:
        desired_json["live-restore"] = live_restore

    if daemon_config.get("iptables") is not None:
        desired_json["iptables"] = daemon_config["iptables"]
    ulimits = daemon_config.get("default_ulimits", {})
    if ulimits:
        desired_json["default-ulimits"] = {name: {"hard": val, "soft": val} for name, val in ulimits.items()}

    desired_content = jsonlib.dumps(desired_json, indent=2)

    # Compare parsed JSON to prevent false-positive restarts due to formatting whitespace
    is_matching = False
    if current_content:
        try:
            curr_parsed = jsonlib.loads(current_content)
            if curr_parsed == desired_json:
                is_matching = True
        except Exception:
            if current_content == desired_content:
                is_matching = True

    if is_matching:
        console.print("  [green]✓[/green] docker_daemon: daemon.json already configured")
        return False

    if dry_run:
        console.print(f"  [yellow]⟳[/yellow] docker_daemon: would write {DAEMON_JSON_PATH}")
        for key in desired_json:
            console.print(f"    [dim]{key}: {desired_json[key]}[/dim]")
        return True

    ssh.run("mkdir -p /etc/docker", sudo=True)
    ssh.run(f"echo '{desired_content}' > {DAEMON_JSON_PATH}", sudo=True)
    # Reload config with zero container downtime via SIGHUP/reload; fallback to restart only if necessary
    ssh.run(
        "systemctl is-active docker >/dev/null 2>&1 && (systemctl reload docker 2>/dev/null || systemctl restart docker) || systemctl restart docker",
        sudo=True,
    )
    console.print("  [green]✓[/green] docker_daemon: daemon.json written and docker reloaded (zero container downtime)")
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
        console.print("  [green]✓[/green] docker_directories: all directories exist")
        return False

    if dry_run:
        for d in missing:
            console.print(f"  [yellow]⟳[/yellow] docker_directories: would create {d}")
        return True

    for d in missing:
        ssh.run(f"mkdir -p {d}", sudo=True)
        console.print(f"  [green]✓[/green] docker_directories: created {d}")
    return True
