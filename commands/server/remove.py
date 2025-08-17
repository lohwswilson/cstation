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
from .inventory_utils import host_exists, get_hosts_by_group, find_host_groups

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
    
    # Define inventory directory path
    inventory_dir = Path("/etc/cstation/ansible/inventory")
    
    # Check if inventory directory exists
    if not inventory_dir.exists():
        console.print(f"[red]Error: Inventory directory not found: {inventory_dir}[/red]")
        console.print("Run [cyan]cstation init[/cyan] to initialize the configuration.")
        raise typer.Exit(1)
    
    # First check if host exists using ansible-inventory
    if not host_exists(server_name, str(inventory_dir)):
        console.print(f"[yellow]Server '{server_name}' not found in inventory[/yellow]")
        
        # Show available servers using inventory utilities
        console.print("\n[blue]Available servers:[/blue]")
        table = Table(show_header=True, header_style="bold blue")
        table.add_column("Group", style="cyan")
        table.add_column("Server", style="green")
        
        groups_data = get_hosts_by_group(str(inventory_dir))
        for group_name, hosts in groups_data.items():
            for host_name in hosts:
                table.add_row(group_name, host_name)
        
        console.print(table)
        return
    
    # Find which groups contain this host
    host_groups = find_host_groups(server_name, str(inventory_dir))
    
    if not host_groups:
        console.print(f"[yellow]Server '{server_name}' not found in any groups[/yellow]")
        return
    
    # Now we need to find and modify the actual YAML files
    # Get all YAML files in the inventory directory
    yaml_files = list(inventory_dir.glob('*.yml')) + list(inventory_dir.glob('*.yaml'))
    
    if not yaml_files:
        console.print(f"[red]Error: No YAML inventory files found in {inventory_dir}[/red]")
        raise typer.Exit(1)
    
    try:
        # Find which files contain the server
        files_to_modify = []
        server_locations = []
        
        for yaml_file in yaml_files:
            with open(yaml_file, 'r') as f:
                inventory = yaml.safe_load(f)
            
            if not inventory:
                continue
            
            # Search for the server in this file
            found_in_file = []
            for group_name, group_data in inventory.items():
                if isinstance(group_data, dict) and 'hosts' in group_data:
                    if server_name in group_data['hosts']:
                        found_in_file.append(group_name)
            
            if found_in_file:
                files_to_modify.append(yaml_file)
                server_locations.extend([(yaml_file, group) for group in found_in_file])
        
        # Show what will be removed
        console.print(f"[yellow]Found server '{server_name}' in {len(server_locations)} location(s):[/yellow]")
        
        table = Table(show_header=True, header_style="bold red")
        table.add_column("File", style="blue")
        table.add_column("Group", style="cyan")
        table.add_column("Server", style="red")
        table.add_column("Configuration", style="yellow")
        
        for yaml_file, group_name in server_locations:
            # Load the file to get server config
            with open(yaml_file, 'r') as f:
                inventory = yaml.safe_load(f)
            
            server_config = inventory[group_name]['hosts'][server_name]
            config_summary = ""
            if isinstance(server_config, dict):
                config_keys = list(server_config.keys())
                config_summary = f"{len(config_keys)} settings: {', '.join(config_keys[:3])}{'...' if len(config_keys) > 3 else ''}"
            else:
                config_summary = "Basic entry"
            
            table.add_row(yaml_file.name, group_name, server_name, config_summary)
        
        console.print(table)
        
        if dry_run:
            console.print("\n[yellow]DRY RUN: No changes would be made[/yellow]")
            return
        
        # Confirmation
        if not force:
            if not Confirm.ask(f"\nAre you sure you want to remove server '{server_name}' from {len(server_locations)} location(s)?"):
                console.print("[blue]Operation cancelled[/blue]")
                raise typer.Exit(0)
        
        # Create backups if requested
        if backup:
            import shutil
            import time
            timestamp = int(time.time())
            for yaml_file in files_to_modify:
                backup_path = yaml_file.with_suffix(f".backup.{timestamp}.yml")
                shutil.copy2(yaml_file, backup_path)
                console.print(f"[green]✓[/green] Backup created: {backup_path}")
        
        # Remove server from all files and groups
        removed_count = 0
        for yaml_file, group_name in server_locations:
            # Load the file
            with open(yaml_file, 'r') as f:
                inventory = yaml.safe_load(f)
            
            # Remove the server
            del inventory[group_name]['hosts'][server_name]
            removed_count += 1
            
            # Write updated inventory back to file
            with open(yaml_file, 'w') as f:
                yaml.dump(inventory, f, default_flow_style=False, sort_keys=False, indent=2)
            
            console.print(f"[green]✓[/green] Removed '{server_name}' from group '{group_name}' in {yaml_file.name}")
        
        console.print(f"\n[bold green]🎉 Successfully removed server '{server_name}' from {removed_count} location(s)[/bold green]")
        console.print(f"[blue]Updated {len(files_to_modify)} inventory file(s)[/blue]")
        
    except yaml.YAMLError as e:
        console.print(f"[red]Error parsing YAML inventory file: {e}[/red]")
        raise typer.Exit(1)
    except PermissionError:
        console.print(f"[red]Error: Permission denied accessing {inventory_path}[/red]")
        console.print("The inventory file is owned by root. Please run the command with sudo:")
        console.print(f"[cyan]sudo cstation server rm {server_name}[/cyan]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error removing server: {e}[/red]")
        raise typer.Exit(1)

if __name__ == "__main__":
    typer.run(server_remove)