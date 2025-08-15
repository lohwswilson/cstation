#!/usr/bin/env python3
"""
Server list command - List hosts from Ansible inventory
"""

import typer
import yaml
from typing import Optional
from pathlib import Path
from rich import print as rprint
from rich.console import Console
from rich.table import Table

console = Console()

def server_list(
    hostname: Optional[str] = typer.Argument(None, help="Hostname to show details for (optional)"),
    inventory_file: Optional[str] = typer.Option(
        "/etc/cstation/ansible/inventory/hosts.yml", 
        "-i", "--inventory", 
        help="Inventory file path"
    )
):
    """
    List servers from Ansible inventory
    """
    inventory_path = Path(inventory_file)
    
    if not inventory_path.exists():
        console.print(f"[red]Error:[/red] Inventory file {inventory_path} does not exist")
        raise typer.Exit(1)
    
    try:
        with open(inventory_path, 'r') as file:
            inventory_data = yaml.safe_load(file)
        
        if not inventory_data:
            console.print(f"[yellow]Warning:[/yellow] Inventory file is empty or invalid")
            return
        
        if hostname:
            # Show specific host with its variables
            console.print(f"[blue]Host details for '{hostname}':[/blue]")
            host_found = False
            
            for group_name, group_data in inventory_data.items():
                if isinstance(group_data, dict) and 'hosts' in group_data:
                    hosts = group_data['hosts']
                    if isinstance(hosts, dict) and hostname in hosts:
                        host_found = True
                        console.print(f"\n[green]Group:[/green] {group_name}")
                        console.print(f"[green]Host:[/green] {hostname}")
                        
                        host_vars = hosts[hostname]
                        if host_vars:
                            console.print("\n[blue]Variables:[/blue]")
                            for var_name, var_value in host_vars.items():
                                console.print(f"  [cyan]{var_name}:[/cyan] {var_value}")
                        break
            
            if not host_found:
                console.print(f"[yellow]Warning:[/yellow] Host '{hostname}' not found in inventory")
        else:
            # Show all hosts in a nice table format
            console.print(f"[blue]Server Inventory ({inventory_path}):[/blue]\n")
            
            table = Table(show_header=True, header_style="bold blue")
            table.add_column("Group", style="green")
            table.add_column("Hostname", style="cyan")
            table.add_column("Connection", style="yellow")
            
            for group_name, group_data in inventory_data.items():
                if isinstance(group_data, dict) and 'hosts' in group_data:
                    hosts = group_data['hosts']
                    if isinstance(hosts, dict):
                        for host_name, host_vars in hosts.items():
                            # Skip 'vars' and other non-host entries
                            if host_name not in ['vars', 'children']:
                                # Extract connection info if available
                                connection_info = ""
                                if host_vars and isinstance(host_vars, dict):
                                    if 'ansible_host' in host_vars:
                                        connection_info = host_vars['ansible_host']
                                    elif 'ansible_connection' in host_vars:
                                        connection_info = host_vars['ansible_connection']
                                
                                table.add_row(group_name, host_name, connection_info)
            
            console.print(table)
            
    except yaml.YAMLError as e:
        console.print(f"[red]Error:[/red] Failed to parse YAML file: {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to read inventory file: {e}")
        raise typer.Exit(1)