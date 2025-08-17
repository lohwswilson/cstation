#!/usr/bin/env python3
"""
List profiles command for server management
"""

import typer
from rich.console import Console
from rich.table import Table
from pathlib import Path
import yaml

console = Console()

def list_profiles():
    """
    List available software profiles.
    """
    profiles_dir = Path("/etc/cstation/service/server")
    
    if not profiles_dir.exists():
        console.print(f"[red]Profiles directory not found: {profiles_dir}[/red]")
        return
    
    table = Table(title="Available Server Profiles")
    table.add_column("Service", style="cyan")
    table.add_column("Description", style="green")
    table.add_column("Packages", style="yellow")
    table.add_column("Services", style="magenta")
    
    for profile_file in profiles_dir.glob("*.yml"):
        profile_name = profile_file.stem
        try:
            with open(profile_file, 'r') as f:
                config = yaml.safe_load(f) or {}
            
            description = config.get('description', 'No description')
            
            # Process packages
            packages = config.get('packages', [])
            package_names = [pkg.get('name', str(pkg)) if isinstance(pkg, dict) else str(pkg) for pkg in packages]
            packages_str = ", ".join(package_names[:3])
            if len(package_names) > 3:
                packages_str += f" (+{len(package_names) - 3} more)"
            
            # Process services
            services = config.get('services', [])
            if services:
                service_names = [svc.get('name', str(svc)) if isinstance(svc, dict) else str(svc) for svc in services]
                services_str = ", ".join(service_names[:3])
                if len(service_names) > 3:
                    services_str += f" (+{len(service_names) - 3} more)"
            else:
                services_str = "None"
            
            table.add_row(profile_name, description, packages_str, services_str)
        except Exception as e:
            table.add_row(profile_name, f"Error: {e}", "", "")
    
    console.print(table)