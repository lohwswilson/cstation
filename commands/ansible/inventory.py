#!/usr/bin/env python3
"""
Ansible inventory command
"""

import typer
import subprocess
import yaml
from typing import Optional
from pathlib import Path
from rich import print as rprint


def ansible_inventory(
    action: Optional[str] = typer.Argument(None, help="Inventory action (list, edit)"),
    hostname: Optional[str] = typer.Argument(None, help="Hostname to show details for (for list action)"),
    inventory_file: Optional[str] = typer.Option("./etc/ansible/inventory/hosts.yml", "-i", "--inventory", help="Inventory file path")
):
    """Manage Ansible inventory"""
    inventory_path = Path(inventory_file)
    
    # If no action is provided, show help
    if action is None:
        rprint("[blue]Usage:[/blue] cstation ansible inventory [ACTION] [HOSTNAME]")
        rprint("\n[blue]Actions:[/blue]")
        rprint("  [green]list[/green]     List all hosts or show details for a specific host")
        rprint("  [green]edit[/green]     Edit the inventory file")
        rprint("\n[blue]Examples:[/blue]")
        rprint("  cstation ansible inventory list")
        rprint("  cstation ansible inventory list sg01")
        rprint("  cstation ansible inventory edit")
        rprint("\n[blue]Options:[/blue]")
        rprint("  -i, --inventory TEXT  Inventory file path [default: ./etc/ansible/inventory/hosts.yml]")
        return
    
    if action == "list":
        if inventory_path.exists():
            try:
                with open(inventory_path, 'r') as file:
                    inventory_data = yaml.safe_load(file)
                
                if not inventory_data:
                    rprint(f"[yellow]Warning:[/yellow] Inventory file is empty or invalid")
                    return
                
                if hostname:
                    # Show specific host with its variables
                    rprint(f"[blue]Host details for '{hostname}':[/blue]")
                    host_found = False
                    
                    for group_name, group_data in inventory_data.items():
                        if isinstance(group_data, dict) and 'hosts' in group_data:
                            hosts = group_data['hosts']
                            if isinstance(hosts, dict) and hostname in hosts:
                                host_found = True
                                rprint(f"\nGroup: {group_name}")
                                rprint(f"Host: {hostname}")
                                
                                host_vars = hosts[hostname]
                                if host_vars:
                                    rprint("Variables:")
                                    for var_name, var_value in host_vars.items():
                                        rprint(f"  {var_name}: {var_value}")
                                break
                    
                    if not host_found:
                        rprint(f"[yellow]Warning:[/yellow] Host '{hostname}' not found in inventory")
                else:
                    # Show all hosts without variables
                    rprint(f"[blue]Inventory ({inventory_path}):[/blue]")
                    
                    for group_name, group_data in inventory_data.items():
                        if isinstance(group_data, dict) and 'hosts' in group_data:
                            rprint(f"\n[{group_name}]")
                            hosts = group_data['hosts']
                            if isinstance(hosts, dict):
                                for host_name in hosts.keys():
                                    # Skip 'vars' and other non-host entries
                                    if host_name not in ['vars', 'children']:
                                        rprint(f"  {host_name}")
                            
            except yaml.YAMLError as e:
                rprint(f"[red]Error:[/red] Failed to parse YAML file: {e}")
            except Exception as e:
                rprint(f"[red]Error:[/red] Failed to read inventory file: {e}")
        else:
            rprint(f"[yellow]Warning:[/yellow] Inventory file {inventory_path} does not exist")
            
    elif action == "edit":
        if not inventory_path.exists():
            rprint(f"[yellow]Warning:[/yellow] Inventory file {inventory_path} does not exist. Creating...")
            inventory_path.parent.mkdir(parents=True, exist_ok=True)
            inventory_path.write_text("[ungrouped]\n")
        
        import os
        editor = os.environ.get('EDITOR', 'vim')
        try:
            subprocess.run([editor, str(inventory_path)], check=True)
            rprint(f"[green]✓[/green] Inventory file edited: {inventory_path}")
        except subprocess.CalledProcessError:
            rprint(f"[red]✗[/red] Failed to open editor for {inventory_path}")
            
    else:
        rprint(f"[red]Error:[/red] Unknown action '{action}'. Use: list, edit")
        raise typer.Exit(1)