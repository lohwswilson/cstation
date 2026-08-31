"""
Lint command module for CStation CLI.
Provides offline pre-flight validation for VPS configs, container fragments,
image recipes, port conflicts, secret bindings, and host platform path rules.
"""

from __future__ import annotations

import os
import sys
import yaml
from typing import Any, Optional, Dict
import typer
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from cstation.config import (
    CSTATION_VPS_DIR,
    CSTATION_IMAGES_DIR,
    CSTATION_DNS_DIR,
    get_vps_secrets,
)
from cstation.models import (
    VPSConfig,
    ContainerConfig,
    DockerImageConfig,
    DNSConfig,
)
from cstation.output import OutputFormat, print_formatted

console = Console()

lint_app = typer.Typer(
    name="lint",
    help="Pre-flight configuration linter & schema validator",
    invoke_without_command=True,
)


def _parse_port_binding(port_str: str) -> tuple[str, int, str]:
    """
    Parse a docker port string like '8069:8069', '127.0.0.1:5432:5432', '80/tcp'.
    Returns (host_ip, host_port, protocol).
    """
    proto = "tcp"
    if "/" in port_str:
        port_str, proto = port_str.split("/", 1)

    parts = port_str.split(":")
    if len(parts) == 1:
        # Single port e.g. 80
        return ("0.0.0.0", int(parts[0]), proto)
    elif len(parts) == 2:
        # host_port:container_port
        return ("0.0.0.0", int(parts[0]), proto)
    elif len(parts) == 3:
        # host_ip:host_port:container_port
        return (parts[0], int(parts[1]), proto)
    return ("0.0.0.0", 0, proto)


def run_lint_checks() -> dict[str, Any]:
    """
    Run all offline linting checks against cstation configs.
    """
    results = {
        "passed": True,
        "total_checks": 0,
        "error_count": 0,
        "warning_count": 0,
        "issues": [],
    }

    def add_issue(target: str, rule: str, severity: str, message: str, file_path: Optional[str] = None):
        results["total_checks"] += 1
        is_error = severity.upper() == "ERROR"
        if is_error:
            results["error_count"] += 1
            results["passed"] = False
        else:
            results["warning_count"] += 1

        results["issues"].append(
            {
                "target": target,
                "rule": rule,
                "severity": severity.upper(),
                "message": message,
                "file": file_path,
            }
        )

    # 1. Check VPS Configs & Containers
    vps_dir = CSTATION_VPS_DIR
    if vps_dir.exists() and vps_dir.is_dir():
        for vps_path in sorted(vps_dir.iterdir()):
            if not vps_path.is_dir():
                continue
            vps_name = vps_path.name
            vps_yaml = vps_path / "vps.yaml"
            vps_config: Optional[VPSConfig] = None

            # Validate vps.yaml
            if vps_yaml.exists():
                results["total_checks"] += 1
                try:
                    raw_vps = yaml.safe_load(vps_yaml.read_text(encoding="utf-8")) or {}
                    vps_config = VPSConfig.model_validate(raw_vps)
                except ValidationError as e:
                    for err in e.errors():
                        field = ".".join(str(loc) for loc in err["loc"])
                        add_issue(vps_name, "schema:vps", "ERROR", f"Field '{field}': {err['msg']}", str(vps_yaml))
                except Exception as e:
                    add_issue(vps_name, "schema:vps", "ERROR", f"Failed to parse YAML: {e}", str(vps_yaml))
            else:
                add_issue(vps_name, "missing:vps.yaml", "WARNING", "No vps.yaml file found in directory", str(vps_path))

            # Validate Containers in VPS
            host_ports: Dict[tuple[str, int, str], str] = {}  # (ip, port, proto) -> container_name
            is_local_mac = (
                vps_name == "local.dev" or (vps_config and vps_config.access.host in ["127.0.0.1", "localhost"])
            ) and sys.platform == "darwin"

            for container_yaml in sorted(vps_path.glob("*.yaml")):
                if container_yaml.name == "vps.yaml":
                    continue
                results["total_checks"] += 1
                c_name = container_yaml.stem
                try:
                    raw_c = yaml.safe_load(container_yaml.read_text(encoding="utf-8")) or {}
                    c_config = ContainerConfig.model_validate(raw_c)
                    c_name = c_config.name or c_config.container_name or container_yaml.stem

                    if not c_config.enabled:
                        continue

                    # Port Conflict Check
                    for port_str in c_config.ports:
                        try:
                            ip, host_p, proto = _parse_port_binding(str(port_str))
                            if host_p == 0:
                                continue

                            # Check collision on 0.0.0.0 or exact IP
                            binding_key = (ip, host_p, proto)
                            wildcard_key = ("0.0.0.0", host_p, proto)

                            if binding_key in host_ports:
                                add_issue(
                                    vps_name,
                                    "conflict:port",
                                    "ERROR",
                                    f"Host port {ip}:{host_p}/{proto} collision between '{c_name}' and '{host_ports[binding_key]}'",
                                    str(container_yaml),
                                )
                            elif ip != "0.0.0.0" and wildcard_key in host_ports:
                                add_issue(
                                    vps_name,
                                    "conflict:port",
                                    "ERROR",
                                    f"Host port {ip}:{host_p}/{proto} conflicts with wildcard 0.0.0.0 binding in '{host_ports[wildcard_key]}'",
                                    str(container_yaml),
                                )
                            else:
                                host_ports[binding_key] = c_name
                        except Exception as pe:
                            add_issue(
                                vps_name,
                                "syntax:port",
                                "WARNING",
                                f"Could not parse port '{port_str}' in container '{c_name}': {pe}",
                                str(container_yaml),
                            )

                    # Secret Reference Check
                    if c_config.secrets:
                        vps_secrets = get_vps_secrets(vps_name, c_name)
                        if vps_config and vps_config.identity and vps_config.identity.name:
                            vps_secrets = {**get_vps_secrets(vps_config.identity.name, c_name), **vps_secrets}
                        for secret_key in c_config.secrets:
                            val = vps_secrets.get(secret_key)
                            if not val and secret_key not in os.environ:
                                add_issue(
                                    vps_name,
                                    "secret:missing",
                                    "WARNING",
                                    f"Required secret '{secret_key}' for container '{c_name}' is missing or empty in config.yaml",
                                    str(container_yaml),
                                )

                    # Host Path Warning for macOS / local
                    if is_local_mac:
                        for vol in c_config.volumes:
                            host_vol = vol.split(":")[0] if ":" in vol else vol
                            if host_vol.startswith(("/var/lib", "/var/log", "/etc")):
                                add_issue(
                                    vps_name,
                                    "platform:path",
                                    "WARNING",
                                    f"Host volume '{host_vol}' on macOS OrbStack/Docker targets VM filesystem instead of Mac. Consider '/Users/...'.",
                                    str(container_yaml),
                                )

                except ValidationError as e:
                    for err in e.errors():
                        field = ".".join(str(loc) for loc in err["loc"])
                        add_issue(
                            vps_name,
                            "schema:container",
                            "ERROR",
                            f"Container '{c_name}' field '{field}': {err['msg']}",
                            str(container_yaml),
                        )
                except Exception as e:
                    add_issue(
                        vps_name,
                        "schema:container",
                        "ERROR",
                        f"Failed to parse container YAML '{c_name}': {e}",
                        str(container_yaml),
                    )

    # 2. Check Docker Image Recipes
    img_dir = CSTATION_IMAGES_DIR
    if img_dir.exists() and img_dir.is_dir():
        for recipe_dir in sorted(img_dir.iterdir()):
            if not recipe_dir.is_dir():
                continue
            recipe_yaml = recipe_dir / "image.yaml"
            if recipe_yaml.exists():
                results["total_checks"] += 1
                try:
                    raw_img = yaml.safe_load(recipe_yaml.read_text(encoding="utf-8")) or {}
                    DockerImageConfig.model_validate(raw_img)
                except ValidationError as e:
                    for err in e.errors():
                        field = ".".join(str(loc) for loc in err["loc"])
                        add_issue(
                            recipe_dir.name, "schema:image", "ERROR", f"Field '{field}': {err['msg']}", str(recipe_yaml)
                        )
                except Exception as e:
                    add_issue(
                        recipe_dir.name, "schema:image", "ERROR", f"Failed to parse image.yaml: {e}", str(recipe_yaml)
                    )

    # 3. Check DNS Zones
    dns_dir = CSTATION_DNS_DIR
    if dns_dir.exists() and dns_dir.is_dir():
        for dns_yaml in sorted(dns_dir.glob("*.yaml")):
            results["total_checks"] += 1
            domain_name = dns_yaml.stem
            try:
                raw_dns = yaml.safe_load(dns_yaml.read_text(encoding="utf-8")) or {}
                DNSConfig.model_validate(raw_dns)
            except ValidationError as e:
                for err in e.errors():
                    field = ".".join(str(loc) for loc in err["loc"])
                    add_issue(domain_name, "schema:dns", "ERROR", f"Field '{field}': {err['msg']}", str(dns_yaml))
            except Exception as e:
                add_issue(
                    domain_name, "schema:dns", "ERROR", f"Failed to parse DNS YAML '{domain_name}': {e}", str(dns_yaml)
                )

    return results


@lint_app.callback(invoke_without_command=True)
def lint_main(
    ctx: typer.Context,
    output: OutputFormat = typer.Option(
        OutputFormat.TABLE,
        "--output",
        "-o",
        help="Output format: table, json, or yaml",
    ),
) -> None:
    """
    Run offline pre-flight validation and linting on all CStation configurations.
    """
    results = run_lint_checks()

    def render_table():
        if not results["issues"]:
            console.print(
                f"[bold green]✓ All configurations validated successfully![/bold green] ({results['total_checks']} checks passed)"
            )
            return

        table = Table(title="CStation Configuration Lint Results", show_header=True, header_style="bold cyan")
        table.add_column("Target / Node", style="bold", width=24)
        table.add_column("Severity", width=10)
        table.add_column("Rule", style="dim", width=18)
        table.add_column("Details", style="white")

        for issue in results["issues"]:
            sev = issue["severity"]
            sev_style = "[bold red]ERROR[/bold red]" if sev == "ERROR" else "[bold yellow]WARN[/bold yellow]"
            table.add_row(
                issue["target"],
                sev_style,
                issue["rule"],
                issue["message"],
            )

        console.print(table)
        console.print(
            f"\nSummary: [bold red]{results['error_count']} Errors[/bold red], "
            f"[bold yellow]{results['warning_count']} Warnings[/bold yellow] "
            f"across {results['total_checks']} items checked."
        )

    print_formatted(results, format_type=output, table_renderer=render_table)

    if not results["passed"]:
        raise typer.Exit(code=1)
