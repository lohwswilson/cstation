#!/usr/bin/env python3
"""
Self-update command for CStation CLI.
Supports PyPI version lookup, structured JSON output, --check-only mode,
and self-upgrades via 'uv tool' and Git checkouts.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import urllib.request
from importlib.metadata import PackageNotFoundError, version as pkg_version
from pathlib import Path
from typing import Optional

import typer
from rich import print as rprint

from ...output import OutputFormat, print_formatted


def _cstation_version() -> str:
    """Read the installed package version."""
    try:
        return pkg_version("cstation")
    except PackageNotFoundError:
        return "1.0.0"


def get_latest_pypi_version(package_name: str = "cstation", timeout: float = 3.0) -> Optional[str]:
    """Fetch the latest release version of a package from PyPI JSON API."""
    url = f"https://pypi.org/pypi/{package_name}/json"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": f"cstation-cli/{_cstation_version()}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                payload = json.loads(response.read().decode("utf-8"))
                return payload.get("info", {}).get("version")
    except Exception:
        return None
    return None


def is_version_newer(latest: str, current: str) -> bool:
    """Compare two version strings, returning True if latest > current."""
    try:
        from packaging.version import parse as parse_version

        return parse_version(latest) > parse_version(current)
    except Exception:
        # Fallback to integer tuple comparison
        def _parse(v: str) -> tuple[int, ...]:
            digits = re.findall(r"\d+", v)
            return tuple(int(d) for d in digits) if digits else (0,)

        return _parse(latest) > _parse(current)


def detect_install_method() -> tuple[str, Optional[Path]]:
    """
    Detect how CStation is currently installed.
    Returns (method_name, path_context) where method_name is one of:
      - 'uv_tool_editable' (installed via uv tool with --editable)
      - 'uv_tool_pypi'     (installed via uv tool from PyPI or remote)
      - 'uv_tool'          (detected in uv tool list without receipt inspection)
      - 'git_checkout'     (running directly within a Git working repository)
      - 'unknown'          (fallback)
    """
    uv_path = shutil.which("uv")
    if uv_path:
        # Check ~/.local/share/uv/tools/cstation/uv-receipt.toml
        uv_tool_receipt = Path.home() / ".local" / "share" / "uv" / "tools" / "cstation" / "uv-receipt.toml"
        if uv_tool_receipt.exists():
            try:
                content = uv_tool_receipt.read_text(encoding="utf-8")
                if "editable =" in content:
                    match = re.search(r'editable\s*=\s*"([^"]+)"', content)
                    editable_path = Path(match.group(1)) if match else None
                    return "uv_tool_editable", editable_path
                return "uv_tool_pypi", None
            except Exception:
                pass

        # Check uv tool list fallback
        try:
            res = subprocess.run(
                [uv_path, "tool", "list"],
                capture_output=True,
                text=True,
                check=False,
            )
            if "cstation" in res.stdout:
                return "uv_tool", None
        except Exception:
            pass

    # Check git repository root
    cstation_pkg_dir = Path(__file__).resolve().parent.parent.parent.parent
    if (cstation_pkg_dir / ".git").exists():
        return "git_checkout", cstation_pkg_dir

    return "unknown", None


def update(
    check_only: bool = typer.Option(
        False,
        "--check-only",
        "-c",
        help="Check for available updates without applying them.",
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.TABLE,
        "--output",
        "-o",
        help="Output format (table, json, yaml).",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force reinstall/upgrade even if already at latest version.",
    ),
):
    """Update CStation CLI to the latest version.

    Supports PyPI registry queries, 'uv tool' upgrades, and Git checkouts.
    """
    current_ver = _cstation_version()
    latest_pypi_ver = get_latest_pypi_version("cstation")
    update_available = (
        is_version_newer(latest_pypi_ver, current_ver) if latest_pypi_ver else False
    )
    install_method, context_path = detect_install_method()

    # Handle --check-only mode
    if check_only:
        data = {
            "installed_version": current_ver,
            "latest_pypi_version": latest_pypi_ver,
            "update_available": update_available,
            "install_method": install_method,
            "status": "update_available" if update_available else "up_to_date",
        }
        if output in (OutputFormat.JSON, OutputFormat.YAML):
            print_formatted(data, format_type=output)
            return

        # Human-readable output
        rprint(f"[bold blue]CStation[/bold blue] current version: [bold cyan]v{current_ver}[/bold cyan]")
        if latest_pypi_ver:
            rprint(f"Latest PyPI version: [bold green]v{latest_pypi_ver}[/bold green]")
            if update_available:
                rprint("[bold yellow]➔ An update is available![/bold yellow] Run [cyan]cstation update[/cyan] to upgrade.")
            else:
                rprint("[bold green]✓ CStation is up to date.[/bold green]")
        else:
            rprint("[dim]Unable to query PyPI (offline or registry unreachable).[/dim]")
        rprint(f"[dim]Installation method: {install_method}[/dim]")
        return

    # Non-check-only mode: perform upgrade
    uv_path = shutil.which("uv")
    success = False
    new_ver = current_ver
    msg = ""

    # 1. uv_tool_editable
    if install_method == "uv_tool_editable" and uv_path:
        repo_dir = context_path or Path(__file__).resolve().parent.parent.parent.parent
        if output not in (OutputFormat.JSON, OutputFormat.YAML):
            rprint(f"[yellow]Detected editable 'uv tool' linked to {repo_dir}.[/yellow]")

        git_path = shutil.which("git")
        git_pulled = False
        if git_path and (repo_dir / ".git").exists():
            if output not in (OutputFormat.JSON, OutputFormat.YAML):
                rprint(f"[yellow]Pulling latest Git changes in {repo_dir}...[/yellow]")
            git_res = subprocess.run(
                [git_path, "-C", str(repo_dir), "pull", "--ff-only"],
                capture_output=True,
                text=True,
                check=False,
            )
            git_pulled = (git_res.returncode == 0)

        # Run uv tool upgrade
        upgrade_cmd = [uv_path, "tool", "upgrade", "cstation"]
        res = subprocess.run(upgrade_cmd, capture_output=True, text=True, check=False)
        if res.returncode == 0:
            success = True
            new_ver = _cstation_version()
            msg = f"CStation editable tool refreshed to v{new_ver}" + (" (git pulled)" if git_pulled else "")
        else:
            msg = f"uv tool upgrade failed: {res.stderr.strip()}"

    # 2. uv_tool (standard PyPI install)
    elif install_method in ("uv_tool_pypi", "uv_tool") and uv_path:
        if output not in (OutputFormat.JSON, OutputFormat.YAML):
            rprint("[yellow]Detected 'uv tool' installation. Upgrading via uv...[/yellow]")
        upgrade_cmd = [uv_path, "tool", "upgrade", "cstation"]
        res = subprocess.run(upgrade_cmd, capture_output=True, text=True, check=False)
        if res.returncode == 0:
            success = True
            new_ver = _cstation_version()
            msg = f"CStation successfully upgraded to v{new_ver}"
        else:
            msg = f"uv tool upgrade failed: {res.stderr.strip()}"

    # 3. git_checkout
    elif install_method == "git_checkout":
        cstation_pkg_dir = context_path or Path(__file__).resolve().parent.parent.parent.parent
        git_path = shutil.which("git")
        if not git_path:
            msg = "Git is not installed or not in PATH."
        else:
            if output not in (OutputFormat.JSON, OutputFormat.YAML):
                rprint(f"[yellow]Detected Git source directory at {cstation_pkg_dir}. Pulling latest changes...[/yellow]")
            res = subprocess.run(
                [git_path, "-C", str(cstation_pkg_dir), "pull", "--ff-only"],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0:
                success = True
                msg = res.stdout.strip() or "Already up to date."
            else:
                msg = f"Git pull failed: {res.stderr.strip()}"

    else:
        msg = "Could not automatically determine installation method. Please update manually via 'uv tool upgrade cstation' or 'git pull'."

    # Output results
    if output in (OutputFormat.JSON, OutputFormat.YAML):
        data = {
            "installed_version": current_ver,
            "new_version": new_ver,
            "success": success,
            "install_method": install_method,
            "message": msg,
        }
        print_formatted(data, format_type=output)
        if not success:
            raise typer.Exit(code=1)
        return

    # Table / Human output
    rprint(f"[bold blue]CStation[/bold blue] current version: [bold cyan]v{current_ver}[/bold cyan]")
    if success:
        rprint(f"[bold green]✓ {msg}[/bold green]")
    else:
        rprint(f"[bold red]✗ Upgrade failed:[/bold red] {msg}")
        raise typer.Exit(code=1)
