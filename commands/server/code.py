#!/usr/bin/env python3
"""
Server code/playbook listing command for server management
"""

import typer
from rich.console import Console
from rich.table import Table
from pathlib import Path

console = Console()

def list_server_code():
    """
    List available Ansible playbooks in the server directory.
    """
    playbooks_dir = Path("/etc/cstation/service/server")
    
    if not playbooks_dir.exists():
        console.print(f"[red]Playbooks directory not found: {playbooks_dir}[/red]")
        return
    
    table = Table(title="Available Server Playbooks")
    table.add_column("Playbook", style="cyan")
    table.add_column("Description", style="green")
    table.add_column("Size", style="yellow")
    table.add_column("Modified", style="magenta")
    
    playbook_files = list(playbooks_dir.glob("*.yml")) + list(playbooks_dir.glob("*.yaml"))
    
    if not playbook_files:
        console.print("[yellow]No playbook files found in the server directory[/yellow]")
        return
    
    for playbook_file in sorted(playbook_files):
        # Remove .yml or .yaml extension for display
        playbook_name = playbook_file.stem
        try:
            # Get file stats
            stat = playbook_file.stat()
            size = f"{stat.st_size} bytes"
            modified = f"{stat.st_mtime:.0f}"
            
            # Try to get description from playbook
            description = "Ansible playbook"
            try:
                with open(playbook_file, 'r') as f:
                    content = f.read()
                    if '# ' in content:
                        # Extract first comment as description
                        lines = content.split('\n')
                        for line in lines:
                            if line.strip().startswith('# ') and not line.strip().startswith('# ---'):
                                description = line.strip()[2:]
                                break
            except:
                pass
            
            table.add_row(playbook_name, description, size, modified)
        except Exception as e:
            table.add_row(playbook_name, f"Error: {e}", "", "")
    
    console.print(table)