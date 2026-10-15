#!/usr/bin/env python3
"""
Self-update command for CStation CLI
"""

import shutil
import subprocess
from importlib.metadata import PackageNotFoundError, version as pkg_version
from pathlib import Path

from rich import print as rprint


def _cstation_version() -> str:
    """Read the installed package version."""
    try:
        return pkg_version("cstation")
    except PackageNotFoundError:
        return "dev"


def update(
    check_only: bool = False,
):
    """Update CStation CLI to the latest version.

    Supports upgrades via 'uv tool' and Git checkouts.
    """
    current_ver = _cstation_version()
    rprint(f"[bold blue]CStation[/bold blue] current version: [bold cyan]v{current_ver}[/bold cyan]")

    uv_path = shutil.which("uv")

    # Method 1: Check if installed as a uv tool
    is_uv_tool = False
    if uv_path:
        try:
            res = subprocess.run(
                [uv_path, "tool", "list"],
                capture_output=True,
                text=True,
                check=False,
            )
            if "cstation" in res.stdout:
                is_uv_tool = True
        except Exception:
            is_uv_tool = False

    if is_uv_tool and uv_path:
        rprint("[yellow]Detected 'uv tool' installation. Upgrading via uv...[/yellow]")
        try:
            cmd = [uv_path, "tool", "upgrade", "cstation"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode == 0:
                new_ver = _cstation_version()
                rprint(f"[bold green]✓ CStation successfully upgraded to v{new_ver}![/bold green]")
                if result.stdout.strip():
                    rprint(f"[dim]{result.stdout.strip()}[/dim]")
            else:
                rprint(f"[bold red]✗ Upgrade failed:[/bold red] {result.stderr.strip()}")
        except Exception as e:
            rprint(f"[bold red]✗ Failed to run uv upgrade:[/bold red] {e}")
        return

    # Method 2: Running from a git checkout (e.g. /opt/cstation or ~/PythonProject/cstation)
    cstation_pkg_dir = Path(__file__).resolve().parent.parent.parent.parent
    git_dir = cstation_pkg_dir / ".git"

    if git_dir.exists():
        rprint(f"[yellow]Detected Git source directory at {cstation_pkg_dir}. Pulling latest changes...[/yellow]")
        git_path = shutil.which("git")
        if not git_path:
            rprint("[bold red]✗ Git is not installed or not in PATH.[/bold red]")
            return

        try:
            result = subprocess.run(
                [git_path, "-C", str(cstation_pkg_dir), "pull", "--ff-only"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                output = result.stdout.strip()
                if "Already up to date" in output:
                    rprint("[bold green]✓ CStation is already up to date.[/bold green]")
                else:
                    rprint(f"[bold green]✓ Successfully pulled updates:[/bold green]\n{output}")
            else:
                rprint(f"[bold red]✗ Git pull failed:[/bold red] {result.stderr.strip()}")
        except Exception as e:
            rprint(f"[bold red]✗ Failed to pull updates:[/bold red] {e}")
        return

    # Fallback instructions
    rprint("[bold yellow]! Could not automatically detect installation method.[/bold yellow]")
    rprint("To upgrade manually, run:")
    rprint("  [cyan]uv tool upgrade cstation[/cyan]  (if installed via uv tool)")
    rprint("  or [cyan]git pull[/cyan] in your cstation repository directory.")
