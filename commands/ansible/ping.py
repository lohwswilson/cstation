#!/usr/bin/env python3
"""
Ansible ping command
"""

import typer
import subprocess
from typing import Optional
from rich import print as rprint


def ansible_ping(
    inventory: Optional[str] = typer.Option(None, "-i", "--inventory", help="Inventory file path"),
    limit: Optional[str] = typer.Option(None, "-l", "--limit", help="Limit to specific hosts")
):
    """Ping all hosts in inventory"""
    cmd = ["ansible", "all", "-m", "ping"]
    
    if inventory:
        cmd.extend(["-i", inventory])
    if limit:
        cmd.extend(["-l", limit])
    
    rprint(f"[blue]Running:[/blue] {' '.join(cmd)}")
    
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        rprint(f"[red]✗[/red] Ansible ping failed with exit code {e.returncode}")
        raise typer.Exit(e.returncode)