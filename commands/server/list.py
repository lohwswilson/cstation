#!/usr/bin/env python3
"""
Server list command - List hosts from Ansible inventory
"""

import typer
from typing import Optional
from rich import print as rprint
from rich.console import Console
from rich.table import Table
from .inventory_utils import get_all_hosts, get_host_info, get_hosts_by_group, host_exists

console = Console()

def server_list(
    hostname: Optional[str] = typer.Argument(None, help="Hostname to show details for (optional)"),
    inventory_path: Optional[str] = typer.Option(
        "/etc/cstation/ansible/inventory", 
        "-i", "--inventory", 
        help="Inventory directory path"
    )
):
    """
    List servers from Ansible inventory
    """
    try:
        if hostname:
            # Show specific host with its variables
            if not host_exists(hostname, inventory_path):
                console.print(f"[yellow]Warning:[/yellow] Host '{hostname}' not found in inventory")
                return
            
            console.print(f"[blue]Host details for '{hostname}':[/blue]")
            
            # Get host information
            host_info = get_host_info(hostname, inventory_path)
            if host_info:
                # Find which groups this host belongs to
                from .inventory_utils import find_host_groups
                groups = find_host_groups(hostname, inventory_path)
                
                if groups:
                    console.print(f"\n[green]Groups:[/green] {', '.join(groups)}")
                console.print(f"[green]Host:[/green] {hostname}")
                
                if host_info:
                    console.print("\n[blue]Variables:[/blue]")
                    for var_name, var_value in host_info.items():
                        console.print(f"  [cyan]{var_name}:[/cyan] {var_value}")
        else:
            # Show all hosts in a nice table format
            console.print(f"[blue]Server Inventory ({inventory_path}):[/blue]\n")
            
            table = Table(show_header=True, header_style="bold blue")
            table.add_column("Group", style="green")
            table.add_column("Hostname", style="cyan")
            table.add_column("Connection", style="yellow")
            
            # Get hosts organized by groups
            groups_data = get_hosts_by_group(inventory_path)
            
            for group_name, hosts in groups_data.items():
                for host_name in hosts:
                    # Get host info to extract connection details
                    host_info = get_host_info(host_name, inventory_path)
                    
                    # Extract connection info if available
                    connection_info = ""
                    if host_info:
                        if 'ansible_host' in host_info:
                            connection_info = host_info['ansible_host']
                        elif 'ansible_connection' in host_info:
                            connection_info = host_info['ansible_connection']
                    
                    table.add_row(group_name, host_name, connection_info)
            
            console.print(table)
            
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to read inventory: {e}")
        raise typer.Exit(1)