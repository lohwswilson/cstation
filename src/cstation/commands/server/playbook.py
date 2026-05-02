#!/usr/bin/env python3
"""
Server playbook management commands
"""

import typer
from rich.console import Console
from rich.table import Table
from pathlib import Path
import subprocess
import os

console = Console()

# Create playbook app
playbook_app = typer.Typer(
    name="playbook",
    help="Ansible playbook management",
    invoke_without_command=True
)

def get_playbook_dir():
    """Get the playbooks directory path"""
    # Try to find playbooks directory - prioritize system location first
    current_dir = Path.cwd()
    playbook_paths = [
        Path("/etc/cstation/ansible/playbooks/server"),
        Path("/etc/cstation/ansible/playbooks"),
        current_dir / "playbooks",
        Path(__file__).parent.parent.parent.parent.parent / "playbooks",
    ]
    
    for path in playbook_paths:
        if path.exists():
            return path
    
    # Default to current directory playbooks
    return current_dir / "playbooks"

def list_server_playbooks():
    """
    List available Ansible playbooks in the server directory.
    """
    playbooks_dir = get_playbook_dir()
    
    if not playbooks_dir.exists():
        console.print(f"[red]Playbooks directory not found: {playbooks_dir}[/red]")
        console.print(f"[yellow]Searched in: {playbooks_dir}[/yellow]")
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

def push_playbook(
    ansible_playbook: str = typer.Argument(..., help="Name of the Ansible playbook to execute"),
    target_host: str = typer.Argument(..., help="Target host to run the playbook on"),
    ask_pass: bool = typer.Option(False, "--ask-pass", "-a",  help="Ask for SSH password authentication"),
    extra_vars: str = typer.Option("", "--extra-vars", "-e", help="Extra variables to pass to ansible-playbook (e.g., 'pw_version=3.0 env=prod')")
):
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
    
    # Check if playbook exists in playbook directory
    playbooks_dir = get_playbook_dir()
    playbook_path = playbooks_dir / ansible_playbook
    
    if not playbook_path.exists():
        console.print(f"[red]Ansible playbook not found: {playbook_path}[/red]")
        # List available playbooks
        available_playbooks = list(playbooks_dir.glob("*.yml")) + list(playbooks_dir.glob("*.yaml"))
        if available_playbooks:
            console.print("[yellow]Available playbooks:[/yellow]")
            for pb in available_playbooks:
                console.print(f"  - {pb.stem}")
        raise typer.Exit(1)
    
    # Determine inventory path - prioritize system location
    inventory_paths = [
        Path("/etc/cstation/ansible/inventory"),
        Path("/etc/cstation/ansible/inventory/hosts.yml"),
        Path("/etc/cstation/ansible/inventory/hosts"),
        playbooks_dir / "inventory" / "hosts.yml",
        playbooks_dir / "inventory" / "hosts",
        playbooks_dir / "inventory.yml"
    ]
    
    inventory_path = None
    for inv_path in inventory_paths:
        if inv_path.exists():
            inventory_path = str(inv_path)
            break
    
    if not inventory_path:
        console.print("[red]No inventory file found[/red]")
        console.print("[yellow]Searched in:[/yellow]")
        for inv_path in inventory_paths:
            console.print(f"  - {inv_path}")
        raise typer.Exit(1)
    
    try:
        # Run ansible playbook
        console.print(f"[yellow]Running playbook '{ansible_playbook}' on {target_host}...[/yellow]")
        
        cmd = [
            "ansible-playbook",
            str(playbook_path),
            "-i", inventory_path,
            "--limit", target_host,
            "-e", f"target_host={target_host}",
            "-v"
        ]
        
        # Add extra variables if provided
        if extra_vars:
            cmd.extend(["-e", extra_vars])
        
        # Add password authentication if requested
        if ask_pass:
            cmd.append("--ask-pass")
        
        # Set environment to use ansible.cfg from system location first
        env = os.environ.copy()
        ansible_cfg_paths = [
            Path("/etc/cstation/ansible/ansible.cfg"),
            playbooks_dir / "ansible.cfg"
        ]
        
        ansible_cfg_path = None
        for cfg_path in ansible_cfg_paths:
            if cfg_path.exists():
                ansible_cfg_path = str(cfg_path)
                break
        
        if ansible_cfg_path:
            env['ANSIBLE_CONFIG'] = ansible_cfg_path
        
        result = subprocess.run(cmd, env=env, cwd=str(playbooks_dir))
        
        if result.returncode == 0:
            console.print(f"[green]✓ Successfully executed playbook '{ansible_playbook}' on {target_host}[/green]")
        else:
            console.print(f"[red]Ansible playbook failed with exit code {result.returncode}[/red]")
            raise typer.Exit(result.returncode)
            
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Failed to run ansible playbook: {e}[/red]")
        raise typer.Exit(1)
    except FileNotFoundError:
        console.print(f"[red]ansible-playbook command not found. Please install Ansible.[/red]")
        raise typer.Exit(1)

# Add commands to the playbook app
playbook_app.command("list", help="List available Ansible playbooks")(list_server_playbooks)
playbook_app.command("push", help="Execute an Ansible playbook on a target host")(push_playbook)

@playbook_app.callback()
def playbook_callback(ctx: typer.Context):
    """Ansible playbook management"""
    if ctx.invoked_subcommand is None:
        # Default to list when no subcommand is provided
        list_server_playbooks()

# Keep the original function name for backward compatibility
list_server_code = list_server_playbooks