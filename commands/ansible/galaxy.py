#!/usr/bin/env python3
"""
Ansible galaxy command
"""

import typer
import subprocess
from typing import Optional
from rich import print as rprint


def ansible_galaxy(
    action: str = typer.Argument(..., help="Galaxy action (install, list, etc.)"),
    role_or_collection: Optional[str] = typer.Argument(None, help="Role or collection name"),
    requirements: Optional[str] = typer.Option(None, "-r", "--requirements", help="Requirements file")
):
    """Manage Ansible Galaxy roles and collections"""
    cmd = ["ansible-galaxy", action]
    
    if role_or_collection:
        cmd.append(role_or_collection)
    if requirements:
        cmd.extend(["-r", requirements])
    
    rprint(f"[blue]Running:[/blue] {' '.join(cmd)}")
    
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        rprint(f"[red]✗[/red] Ansible Galaxy command failed with exit code {e.returncode}")
        raise typer.Exit(e.returncode)