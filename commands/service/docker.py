#!/usr/bin/env python3
"""
Docker profiles listing command for service management
"""

import yaml
from pathlib import Path
from typing import Optional
import subprocess
import os

import typer
from rich.console import Console
from rich.table import Table

console = Console()

def list_docker_profiles():
    """
    List available Ansible playbooks in the docker directory.
    """
    playbooks_dir = Path("/etc/cstation/service/docker")
    
    if not playbooks_dir.exists():
        console.print(f"[red]Playbooks directory not found: {playbooks_dir}[/red]")
        return
    
    table = Table(title="Available Docker Playbooks")
    table.add_column("Playbook", style="cyan")
    table.add_column("Description", style="green")
    table.add_column("Size", style="yellow")
    table.add_column("Modified", style="magenta")
    
    playbook_files = list(playbooks_dir.glob("*.yml")) + list(playbooks_dir.glob("*.yaml"))
    
    if not playbook_files:
        console.print("[yellow]No playbook files found in the docker directory[/yellow]")
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


def push_docker(ansible_playbook: str, target_host: str):
    """
    Execute an Ansible playbook from docker directory on a specific target host.
    """
    # Check if target host exists in inventory
    from ..server.inventory_utils import get_host_info
    
    host_info = get_host_info(target_host)
    if not host_info:
        console.print(f"[red]Host '{target_host}' not found in inventory[/red]")
        raise typer.Exit(1)
    
    # Automatically append .yml extension if not provided
    if not ansible_playbook.endswith(('.yml', '.yaml')):
        ansible_playbook = f"{ansible_playbook}.yml"
    
    # Check if playbook exists in docker directory
    playbook_path = Path(f"/etc/cstation/service/docker/{ansible_playbook}")
    if not playbook_path.exists():
        console.print(f"[red]Ansible playbook not found: {playbook_path}[/red]")
        raise typer.Exit(1)
    
    try:
        # Run ansible playbook
        console.print(f"[yellow]Running docker playbook '{ansible_playbook}' on {target_host}...[/yellow]")
        
        cmd = [
            "ansible-playbook",
            str(playbook_path),
            "-i", "/etc/cstation/ansible/inventory",
            "--limit", target_host,
            "-v"
        ]
        
        # Set environment to use our ansible.cfg
        env = os.environ.copy()
        env['ANSIBLE_CONFIG'] = '/etc/cstation/ansible/ansible.cfg'
        
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        if result.returncode == 0:
            console.print(f"[green]✓ Successfully executed docker playbook '{ansible_playbook}' on {target_host}[/green]")
            if result.stdout:
                console.print("[dim]Ansible output:[/dim]")
                console.print(result.stdout)
        else:
            console.print(f"[red]Ansible playbook failed:[/red]")
            if result.stderr:
                console.print(result.stderr)
            if result.stdout:
                console.print(result.stdout)
            raise typer.Exit(1)
            
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Failed to run ansible playbook: {e}[/red]")
        raise typer.Exit(1)
    except FileNotFoundError:
        console.print(f"[red]ansible-playbook command not found. Please install Ansible.[/red]")
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