#!/usr/bin/env python3
"""
Ansible playbook command
"""

import typer
import subprocess
from typing import Optional
from pathlib import Path
from rich import print as rprint


def run_playbook(
    playbook: str = typer.Argument(..., help="Path to the Ansible playbook"),
    inventory: Optional[str] = typer.Option(None, "-i", "--inventory", help="Inventory file path"),
    limit: Optional[str] = typer.Option(None, "-l", "--limit", help="Limit to specific hosts"),
    tags: Optional[str] = typer.Option(None, "-t", "--tags", help="Run only tasks with specific tags"),
    check: bool = typer.Option(False, "--check", help="Run in check mode (dry run)"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Verbose output")
):
    """Run an Ansible playbook"""
    if not Path(playbook).exists():
        rprint(f"[red]Error:[/red] Playbook '{playbook}' not found")
        raise typer.Exit(1)
    
    cmd = ["ansible-playbook", playbook]
    
    if inventory:
        cmd.extend(["-i", inventory])
    if limit:
        cmd.extend(["-l", limit])
    if tags:
        cmd.extend(["-t", tags])
    if check:
        cmd.append("--check")
    if verbose:
        cmd.append("-v")
    
    rprint(f"[blue]Running:[/blue] {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True)
        rprint("[green]✓[/green] Playbook executed successfully")
    except subprocess.CalledProcessError as e:
        rprint(f"[red]✗[/red] Playbook execution failed with exit code {e.returncode}")
        raise typer.Exit(e.returncode)