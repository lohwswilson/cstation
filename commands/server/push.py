#!/usr/bin/env python3
"""
Server push command for deploying Ansible playbooks
"""

import typer
from rich.console import Console
from pathlib import Path
import subprocess
import os

console = Console()

def push_server(ansible_playbook: str, target_host: str):
    """
    Execute an Ansible playbook on a specific target host.
    """
    # Check if target host exists in inventory
    from .inventory_utils import get_host_info
    
    host_info = get_host_info(target_host)
    if not host_info:
        console.print(f"[red]Host '{target_host}' not found in inventory[/red]")
        raise typer.Exit(1)
    
    # Automatically append .yml extension if not provided
    if not ansible_playbook.endswith(('.yml', '.yaml')):
        ansible_playbook = f"{ansible_playbook}.yml"
    
    # Check if playbook exists in server directory
    playbook_path = Path(f"/etc/cstation/service/server/{ansible_playbook}")
    if not playbook_path.exists():
        console.print(f"[red]Ansible playbook not found: {playbook_path}[/red]")
        raise typer.Exit(1)
    
    try:
        # Run ansible playbook
        console.print(f"[yellow]Running playbook '{ansible_playbook}' on {target_host}...[/yellow]")
        
        cmd = [
            "ansible-playbook",
            str(playbook_path),
            "-i", "/etc/cstation/ansible/inventory",
            "--limit", target_host,
            "-v"
        ]
        
        # Set environment to use our ansible.cfg
        env = os.environ.copy()
        env['ANSIBLE_CONFIG'] = '/etc/cstation/ansible/ansible.cfg'
        
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        if result.returncode == 0:
            console.print(f"[green]✓ Successfully executed playbook '{ansible_playbook}' on {target_host}[/green]")
            if result.stdout:
                console.print("[dim]Ansible output:[/dim]")
                console.print(result.stdout)
        else:
            console.print(f"[red]Ansible playbook failed:[/red]")
            if result.stderr:
                console.print(result.stderr)
            if result.stdout:
                console.print(result.stdout)
            raise typer.Exit(1)
            
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Failed to run ansible playbook: {e}[/red]")
        raise typer.Exit(1)
    except FileNotFoundError:
        console.print(f"[red]ansible-playbook command not found. Please install Ansible.[/red]")
        raise typer.Exit(1)