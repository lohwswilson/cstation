#!/usr/bin/env python3
"""
Server status and health check commands
"""

import subprocess
import typer
from typing import Optional
from rich import print as rprint
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

def server_status(
    hostname: Optional[str] = typer.Argument(None, help="Target hostname from inventory (optional - shows all if not specified)"),
    inventory: Optional[str] = typer.Option(
        "etc/ansible/inventory/hosts.yml", 
        "-i", "--inventory", 
        help="Inventory file path"
    ),
    check_services: bool = typer.Option(
        False,
        "--services",
        help="Check common services status (docker, nginx, etc.)"
    )
):
    """
    Check server status and health using Ansible
    """
    
    # Create ansible ad-hoc command
    target = hostname if hostname else "all"
    
    console.print(Panel.fit(
        f"[bold]Checking server status for: {target}[/bold]\n"
        f"Inventory: {inventory}",
        title="Server Status Check",
        border_style="blue"
    ))
    
    # Basic system info check
    console.print("\n[yellow]Gathering system information...[/yellow]")
    
    try:
        # Run ansible setup module to gather facts
        cmd = [
            "ansible",
            target,
            "-i", inventory,
            "-m", "setup",
            "--tree", "/tmp/ansible_facts"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            console.print("[green]✓ System information gathered successfully[/green]")
            
            # Parse and display key information
            lines = result.stdout.split('\n')
            for line in lines:
                if 'SUCCESS' in line and '=>' in line:
                    host = line.split()[0]
                    console.print(f"[green]✓ {host} - Online[/green]")
        else:
            console.print(f"[red]Failed to gather system information:[/red]")
            console.print(result.stderr)
            
    except FileNotFoundError:
        console.print(f"[red]ansible command not found. Please install Ansible.[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error running ansible command: {e}[/red]")
        raise typer.Exit(1)
    
    # Check services if requested
    if check_services:
        console.print("\n[yellow]Checking common services...[/yellow]")
        
        services = ["docker", "nginx", "postgresql", "ssh"]
        
        for service in services:
            try:
                cmd = [
                    "ansible",
                    target,
                    "-i", inventory,
                    "-m", "service_facts"
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    console.print(f"[green]✓ Service check completed[/green]")
                else:
                    console.print(f"[yellow]⚠ Some services may not be available[/yellow]")
                    
            except Exception as e:
                console.print(f"[red]Error checking services: {e}[/red]")
    
    console.print("\n[green]Server status check completed![/green]")


def server_uptime(
    hostname: Optional[str] = typer.Argument(None, help="Target hostname from inventory (optional - shows all if not specified)"),
    inventory: Optional[str] = typer.Option(
        "etc/ansible/inventory/hosts.yml", 
        "-i", "--inventory", 
        help="Inventory file path"
    )
):
    """
    Check server uptime using Ansible
    """
    
    target = hostname if hostname else "all"
    
    console.print(Panel.fit(
        f"[bold]Checking uptime for: {target}[/bold]\n"
        f"Inventory: {inventory}",
        title="Server Uptime",
        border_style="green"
    ))
    
    try:
        # Run ansible command to get uptime
        cmd = [
            "ansible",
            target,
            "-i", inventory,
            "-m", "command",
            "-a", "uptime"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            console.print("\n[green]Server Uptime Information:[/green]")
            console.print(result.stdout)
        else:
            console.print(f"[red]Failed to get uptime information:[/red]")
            console.print(result.stderr)
            
    except FileNotFoundError:
        console.print(f"[red]ansible command not found. Please install Ansible.[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error running ansible command: {e}[/red]")
        raise typer.Exit(1)