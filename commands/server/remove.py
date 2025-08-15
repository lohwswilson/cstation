#!/usr/bin/env python3
"""
Server remove command for CStation CLI
Removes server entries from Ansible inventory
"""

import os
from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table

console = Console()

def server_remove(
    server_name: str = typer.Argument(..., help="Name of the server to remove from inventory"),
    force: bool = typer.Option(False, "--force", "-f", help="Force removal without confirmation"),
    backup: bool = typer.Option(True, "--backup/--no-backup", help="Create backup before modification"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be removed without executing")
):
    """
    Remove a server entry from the Ansible inventory.
    
    This command will:
    - Search for the server in all inventory groups
    - Remove the server entry and its configuration
    - Optionally create a backup of the inventory file
    - Show confirmation before making changes
    """
    
    # Define inventory file path
    inventory_path = Path("/etc/cstation/ansible/inventory/hosts.yml")
    
    # Check if inventory file exists
    if not inventory_path.exists():
        console.print(f"[red]Error: Inventory file not found: {inventory_path}[/red]")
        console.print("Run [cyan]cstation init[/cyan] to initialize the configuration.")
        raise typer.Exit(1)
    
    try:
        # Load inventory file
        with open(inventory_path, 'r') as f:
            inventory = yaml.safe_load(f)
        
        if not inventory:
            console.print("[yellow]Warning: Inventory file is empty[/yellow]")
            raise typer.Exit(0)
        
        # Search for the server in all groups
        found_groups = []
        for group_name, group_data in inventory.items():
            if isinstance(group_data, dict) and 'hosts' in group_data:
                if server_name in group_data['hosts']:
                    found_groups.append(group_name)
        
        if not found_groups:
            console.print(f"[yellow]Server '{server_name}' not found in inventory[/yellow]")
            
            # Show available servers
            console.print("\n[blue]Available servers:[/blue]")
            table = Table(show_header=True, header_style="bold blue")
            table.add_column("Group", style="cyan")
            table.add_column("Server", style="green")
            table.add_column("Host", style="yellow")
            
            for group_name, group_data in inventory.items():
                if isinstance(group_data, dict) and 'hosts' in group_data:
                    for host_name, host_data in group_data['hosts'].items():
                        ansible_host = host_data.get('ansible_host', 'N/A') if isinstance(host_data, dict) else 'N/A'
                        table.add_row(group_name, host_name, ansible_host)
            
            console.print(table)
            return
        
        # Show what will be removed
        console.print(f"[yellow]Found server '{server_name}' in {len(found_groups)} group(s):[/yellow]")
        
        table = Table(show_header=True, header_style="bold red")
        table.add_column("Group", style="cyan")
        table.add_column("Server", style="red")
        table.add_column("Configuration", style="yellow")
        
        for group_name in found_groups:
            server_config = inventory[group_name]['hosts'][server_name]
            config_summary = ""
            if isinstance(server_config, dict):
                config_keys = list(server_config.keys())
                config_summary = f"{len(config_keys)} settings: {', '.join(config_keys[:3])}{'...' if len(config_keys) > 3 else ''}"
            else:
                config_summary = "Basic entry"
            
            table.add_row(group_name, server_name, config_summary)
        
        console.print(table)
        
        if dry_run:
            console.print("\n[yellow]DRY RUN: No changes would be made[/yellow]")
            return
        
        # Confirmation
        if not force:
            if not Confirm.ask(f"\nAre you sure you want to remove server '{server_name}' from {len(found_groups)} group(s)?"):
                console.print("[blue]Operation cancelled[/blue]")
                raise typer.Exit(0)
        
        # Create backup if requested
        if backup:
            backup_path = inventory_path.with_suffix(f".backup.{int(__import__('time').time())}.yml")
            import shutil
            shutil.copy2(inventory_path, backup_path)
            console.print(f"[green]✓[/green] Backup created: {backup_path}")
        
        # Remove server from all groups
        removed_count = 0
        for group_name in found_groups:
            del inventory[group_name]['hosts'][server_name]
            removed_count += 1
            console.print(f"[green]✓[/green] Removed '{server_name}' from group '{group_name}'")
        
        # Write updated inventory back to file
        with open(inventory_path, 'w') as f:
            yaml.dump(inventory, f, default_flow_style=False, sort_keys=False, indent=2)
        
        console.print(f"\n[bold green]🎉 Successfully removed server '{server_name}' from {removed_count} group(s)[/bold green]")
        console.print(f"[blue]Updated inventory file: {inventory_path}[/blue]")
        
    except yaml.YAMLError as e:
        console.print(f"[red]Error parsing YAML inventory file: {e}[/red]")
        raise typer.Exit(1)
    except PermissionError:
        console.print(f"[red]Error: Permission denied accessing {inventory_path}[/red]")
        console.print("Make sure you have write permissions or run with appropriate privileges.")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error removing server: {e}[/red]")
        raise typer.Exit(1)

if __name__ == "__main__":
    typer.run(server_remove)