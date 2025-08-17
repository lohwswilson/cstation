#!/usr/bin/env python3
"""
Docker profiles listing command for service management
"""

import yaml
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

console = Console()

def list_docker_profiles(
    profile_name: Optional[str] = typer.Argument(None, help="Specific profile name to display details"),
    containers_only: bool = typer.Option(False, "--containers-only", "-c", help="Show only container profiles"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output")
):
    """
    List available Docker container profiles or show details of a specific profile.
    
    Examples:
    - cstation service docker ls
    - cstation service docker ls portainer
    - cstation service docker ls --containers-only
    """
    try:
        if profile_name:
            # Show specific profile details
            show_profile_details(profile_name, verbose)
        else:
            # List all available profiles
            list_available_profiles(containers_only, verbose)
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        raise typer.Exit(1)

def list_available_profiles(containers_only: bool, verbose: bool):
    """
    List all available Docker container profiles.
    """
    profiles_dir = Path("/etc/cstation/service/server")
    containers_dir = Path("/etc/cstation/service/docker")
    
    console.print("\n[bold blue]📋 Available Docker Profiles[/bold blue]")
    
    # Create table for profiles
    table = Table(title="Docker Container Profiles")
    table.add_column("Docker Service", style="cyan")
    table.add_column("Location", style="green")
    table.add_column("Description", style="yellow")
    table.add_column("Containers", style="magenta")
    
    profiles_found = False
    
    # Check containers directory first
    if containers_dir.exists():
        for profile_file in containers_dir.glob("*.yml"):
            profile_name = profile_file.stem
            location = "containers/"
            
            # Load profile to get description and container count
            try:
                with open(profile_file, 'r') as f:
                    profile_data = yaml.safe_load(f) or {}
                description = profile_data.get('description', 'No description')
                containers = profile_data.get('containers', {})
                container_count = len(containers)
                
                profiles_found = True
                table.add_row(
                    profile_name,
                    location,
                    description,
                    str(container_count)
                )
            except Exception as e:
                table.add_row(profile_name, location, f"Error: {e}", "0")
    
    # Check main profiles directory if not containers-only
    if not containers_only and profiles_dir.exists():
        for profile_file in profiles_dir.glob("*.yml"):
            profile_name = profile_file.stem
            location = "server/"
            
            # Load profile to check if it has containers
            try:
                with open(profile_file, 'r') as f:
                    profile_data = yaml.safe_load(f) or {}
                
                # Only show if it has containers defined
                containers = profile_data.get('containers', {})
                if containers:
                    description = profile_data.get('description', 'No description')
                    container_count = len(containers)
                    
                    profiles_found = True
                    table.add_row(
                        profile_name,
                        location,
                        description,
                        str(container_count)
                    )
            except Exception as e:
                # Skip profiles that can't be loaded
                continue
    
    if profiles_found:
        console.print(table)
        console.print("\n[dim]💡 Use 'cstation service docker ls <profile_name>' to see detailed container information[/dim]")
    else:
        console.print("[yellow]⚠️  No Docker container profiles found[/yellow]")
        console.print("[dim]Profiles should be located in:[/dim]")
        console.print(f"[dim]  • {containers_dir}[/dim]")
        console.print(f"[dim]  • {profiles_dir}[/dim]")

def show_profile_details(profile_name: str, verbose: bool):
    """
    Show detailed information about a specific Docker profile.
    """
    # Look for profile in containers directory first, then main profiles
    containers_path = Path(f"/etc/cstation/service/docker/{profile_name}.yml")
    main_path = Path(f"/etc/cstation/service/server/{profile_name}.yml")
    
    profile_path = None
    location = None
    
    if containers_path.exists():
        profile_path = containers_path
        location = "containers"
    elif main_path.exists():
        profile_path = main_path
        location = "server"
    else:
        console.print(f"[red]❌ Profile '{profile_name}' not found[/red]")
        console.print("[dim]Available locations:[/dim]")
        console.print(f"[dim]  • {containers_path}[/dim]")
        console.print(f"[dim]  • {main_path}[/dim]")
        raise typer.Exit(1)
    
    try:
        with open(profile_path, 'r') as f:
            profile_data = yaml.safe_load(f) or {}
    except Exception as e:
        console.print(f"[red]❌ Error loading profile: {e}[/red]")
        raise typer.Exit(1)
    
    # Display profile header
    console.print(f"\n[bold blue]🐳 Docker Profile: {profile_name}[/bold blue]")
    console.print(f"[dim]Location: /etc/cstation/service/{location}/{profile_name}.yml[/dim]")
    
    # Show description
    description = profile_data.get('description', 'No description provided')
    console.print(f"\n[bold]Description:[/bold] {description}")
    
    # Show containers
    containers = profile_data.get('containers', {})
    if containers:
        console.print(f"\n[bold green]📦 Containers ({len(containers)}):[/bold green]")
        display_container_details(containers)
    else:
        console.print("\n[yellow]⚠️  No containers defined in this profile[/yellow]")
    
    # Show additional profile information if verbose
    if verbose:
        console.print("\n[bold]📋 Full Profile Configuration:[/bold]")
        console.print(yaml.dump(profile_data, default_flow_style=False, indent=2))

def display_container_details(containers: dict, variables: dict = None):
    """
    Display detailed container information in a table format.
    """
    if not containers:
        console.print("[yellow]No containers defined[/yellow]")
        return
    
    table = Table(title="Container Details")
    table.add_column("Container", style="cyan")
    table.add_column("Image", style="green")
    table.add_column("Ports", style="yellow")
    table.add_column("Volumes", style="magenta")
    table.add_column("Environment", style="blue")
    
    for container_name, container_config in containers.items():
        # Handle both dict and string container definitions
        if isinstance(container_config, str):
            # Simple string definition (just image name)
            image = container_config
            ports = "-"
            volumes = "-"
            env_vars = "-"
        else:
            # Full container configuration
            image = container_config.get('image', 'Not specified')
            
            # Format ports
            ports_list = container_config.get('ports', [])
            if ports_list:
                ports = ", ".join([f"{p['host']}:{p['container']}" if isinstance(p, dict) else str(p) for p in ports_list])
            else:
                ports = "-"
            
            # Format volumes
            volumes_list = container_config.get('volumes', [])
            if volumes_list:
                volumes = ", ".join([f"{v['host']}:{v['container']}" if isinstance(v, dict) else str(v) for v in volumes_list[:2]])
                if len(volumes_list) > 2:
                    volumes += f" (+{len(volumes_list) - 2} more)"
            else:
                volumes = "-"
            
            # Format environment variables
            env_dict = container_config.get('environment', {})
            if env_dict:
                env_vars = ", ".join([f"{k}={v}" for k, v in list(env_dict.items())[:2]])
                if len(env_dict) > 2:
                    env_vars += f" (+{len(env_dict) - 2} more)"
            else:
                env_vars = "-"
        
        table.add_row(container_name, image, ports, volumes, env_vars)
    
    console.print(table)