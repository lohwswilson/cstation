#!/usr/bin/env python3
"""
Server status and health check commands
"""

import os
import subprocess
import typer
from typing import Optional, List
from rich import print as rprint
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from .inventory_utils import get_all_hosts, host_exists

console = Console()



def server_status(
    hostname: Optional[str] = typer.Argument(None, help="Target hostname from inventory (optional - shows all if not specified)"),
    inventory_path: Optional[str] = typer.Option(
        "/etc/cstation/ansible/inventory", 
        "-i", "--inventory", 
        help="Inventory directory path"
    ),
    check_services: bool = typer.Option(
        False,
        "--services",
        help="Check common services status (nginx, postgresql, etc.)"
    ),
    show_uptime: bool = typer.Option(
        True,
        "--uptime/--no-uptime",
        help="Include uptime information in status check"
    )
):
    """
    Check server status, health, and uptime using Ansible
    """
    
    # Get hosts from inventory using ansible-inventory
    if hostname:
        if not host_exists(hostname, inventory_path):
            console.print(f"[red]Host '{hostname}' not found in inventory[/red]")
            raise typer.Exit(1)
        hosts_list = [hostname]
    else:
        hosts_list = get_all_hosts(inventory_path)
        if not hosts_list:
            console.print(f"[red]No hosts found in inventory[/red]")
            raise typer.Exit(1)
    
    target = hostname if hostname else "all"
    
    console.print(Panel.fit(
        f"[bold]Checking server status for: {target}[/bold]\n"
        f"Inventory: {inventory_path}\n"
        f"Hosts found: {', '.join(hosts_list)}",
        title="Server Status Check",
        border_style="blue"
    ))
    
    # Basic system info check
    console.print("\n[yellow]Gathering system information...[/yellow]")
    
    # Create a table to display combined status and uptime information
    table = Table(title="Server Status and Uptime Information")
    table.add_column("Host", style="cyan", no_wrap=True)
    table.add_column("Status", style="bold")
    if show_uptime:
        table.add_column("Uptime", style="green")
    
    # Dictionary to store host information
    host_info = {}
    
    # Initialize host_info with all hosts from inventory
    for host in hosts_list:
        host_info[host] = {"status": "Unknown", "uptime": "N/A"}
    
    try:
        # Run ansible setup module to gather facts
        cmd = [
            "ansible",
            target,
            "-i", inventory_path,
            "-m", "setup"
        ]
        
        # Create environment without ANSIBLE_CONFIG to get simple output format
        env = os.environ.copy()
        if 'ANSIBLE_CONFIG' in env:
            del env['ANSIBLE_CONFIG']
        
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        
        # Process output regardless of return code (ansible returns 4 for unreachable hosts)
        if result.stdout:
            console.print("[green]✓ System information gathered (some hosts may be unreachable)[/green]")
            
            # Parse and update host status information
            lines = result.stdout.split('\n')
            
            for line in lines:
                 # Look for SUCCESS indicators
                 if 'SUCCESS' in line:
                     # Extract hostname from SUCCESS line
                     parts = line.split()
                     if len(parts) > 0:
                         host = parts[0].strip()
                         # Only process if it's a valid host from our inventory
                         if host in hosts_list:
                             host_info[host]["status"] = "[green]Online[/green]"
                 # Look for UNREACHABLE indicators
                 elif 'UNREACHABLE' in line:
                     parts = line.split()
                     if len(parts) > 0:
                         host = parts[0].strip()
                         # Only process if it's a valid host from our inventory
                         if host in hosts_list:
                             host_info[host]["status"] = "[red]Unreachable[/red]"
                 # Look for FAILED indicators
                 elif 'FAILED' in line:
                     parts = line.split()
                     if len(parts) > 0:
                         host = parts[0].strip()
                         # Only process if it's a valid host from our inventory
                         if host in hosts_list:
                             host_info[host]["status"] = "[yellow]Failed[/yellow]"
        else:
            console.print(f"[red]Failed to gather system information:[/red]")
            if result.stderr:
                console.print(result.stderr)
            else:
                console.print("No output received from ansible command")
            
    except FileNotFoundError:
        console.print(f"[red]ansible command not found. Please install Ansible.[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error running ansible command: {e}[/red]")
        raise typer.Exit(1)
    
    # Check services if requested
    if check_services:
        console.print("\n[yellow]Checking common services...[/yellow]")
        
        services = ["nginx", "postgresql", "ssh"]
        
        for service in services:
            try:
                cmd = [
                    "ansible",
                    target,
                    "-i", inventory_path,
                    "-m", "service_facts"
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    console.print(f"[green]✓ Service check completed[/green]")
                else:
                    console.print(f"[yellow]⚠ Some services may not be available[/yellow]")
                    
            except Exception as e:
                console.print(f"[red]Error checking services: {e}[/red]")
    
    # Gather uptime information if requested
    if show_uptime:
        console.print("\n[yellow]Gathering uptime information...[/yellow]")
        
        try:
            # Run ansible command to get uptime
            cmd = [
                "ansible",
                target,
                "-i", inventory_path,
                "-m", "command",
                "-a", "uptime"
            ]
            
            # Create environment without ANSIBLE_CONFIG to get simple output format
            env = os.environ.copy()
            if 'ANSIBLE_CONFIG' in env:
                del env['ANSIBLE_CONFIG']
            
            result = subprocess.run(cmd, capture_output=True, text=True, env=env)
            
            if result.returncode == 0 or result.stdout:
                # Parse and update uptime information in host_info
                lines = result.stdout.split('\n')
                i = 0
                while i < len(lines):
                    line = lines[i].strip()
                    if line:
                        if 'CHANGED | rc=0 >>' in line:
                            # Extract hostname
                            parts = line.split(' | CHANGED | rc=0 >>')
                            if len(parts) >= 1:
                                host = parts[0].strip()
                                # Only process if it's a valid host from our inventory
                                if host in hosts_list:
                                    # Get uptime info from the same line or next line
                                    if len(parts) == 2 and parts[1].strip():
                                        uptime_info = parts[1].strip()
                                    elif i + 1 < len(lines) and lines[i + 1].strip():
                                        uptime_info = lines[i + 1].strip()
                                        i += 1  # Skip the next line as we've processed it
                                    else:
                                        uptime_info = "No uptime data"
                                    host_info[host]["uptime"] = uptime_info
                        elif 'UNREACHABLE' in line:
                            # Check if this is for a valid host from our inventory
                            parts = line.split(' | UNREACHABLE')
                            if len(parts) > 0:
                                host = parts[0].strip()
                                if host in hosts_list:
                                    host_info[host]["uptime"] = "[red]Unreachable[/red]"
                        elif 'FAILED' in line:
                            # Check if this is for a valid host from our inventory
                            parts = line.split(' | FAILED')
                            if len(parts) > 0:
                                host = parts[0].strip()
                                if host in hosts_list:
                                    host_info[host]["uptime"] = "[yellow]Failed[/yellow]"
                    i += 1
            else:
                console.print(f"[yellow]⚠ Could not retrieve uptime for some hosts[/yellow]")
                if result.stderr:
                    console.print(f"[red]{result.stderr}[/red]")
                    
        except Exception as e:
            console.print(f"[red]Error getting uptime information: {e}[/red]")
    
    # Display the combined table
    console.print("\n")
    for host in sorted(hosts_list):
        if show_uptime:
            table.add_row(host, host_info[host]["status"], host_info[host]["uptime"])
        else:
            table.add_row(host, host_info[host]["status"])
    
    console.print(table)
    
    console.print("\n[green]Server status check completed![/green]")