#!/usr/bin/env python3
"""
Version command for CStation CLI
"""

import typer
from rich import print as rprint


def version():
    """Show CStation version"""
    rprint("[bold blue]CStation[/bold blue] v0.1.0")
    rprint("Infrastructure Management CLI for DevOps")