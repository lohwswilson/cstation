#!/usr/bin/env python3
"""
Version command for CStation CLI
"""

from importlib.metadata import PackageNotFoundError, version as pkg_version

from rich import print as rprint


def _cstation_version() -> str:
    """Read the installed package version, falling back for source checkouts."""
    try:
        return pkg_version("cstation")
    except PackageNotFoundError:
        return "unknown"


def version():
    """Show CStation version"""
    rprint(f"[bold blue]CStation[/bold blue] v{_cstation_version()}")
    rprint("Infrastructure Management CLI for DevOps")
