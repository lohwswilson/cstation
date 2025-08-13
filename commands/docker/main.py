#!/usr/bin/env python3
"""
Docker command module for CStation CLI
Manages Docker container deployment using Ansible profiles
"""

import os
import tempfile
import subprocess
import yaml
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

console = Console()

# Create Docker app
docker_app = typer.Typer(
    name="docker", 
    help="Docker container management", 
    invoke_without_command=True
)

@docker_app.command("deploy")
def deploy_containers(
    target: str = typer.Argument(..., help="Target server or 'all' for all servers"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Software profile containing container definitions"),
    inventory: Optional[str] = typer.Option(None, "--inventory", "-i", help="Path to Ansible inventory file"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what containers would be deployed without executing"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output")
):
    """
    Deploy Docker containers on servers using Ansible profiles.
    
    Examples:
    - cstation docker deploy sg01 --profile database_server
    - cstation docker deploy all --profile odoo_app --dry-run
    """
    try:
        # Set default inventory path
        if not inventory:
            inventory = "./etc/ansible/inventory/hosts.yml"
        
        # Validate inventory file exists
        if not Path(inventory).exists():
            console.print(f"[red]Error: Inventory file not found: {inventory}[/red]")
            raise typer.Exit(1)
        
        # Validate profile is provided
        if not profile:
            console.print("[red]Error: Profile is required. Use --profile to specify a profile with container definitions.[/red]")
            raise typer.Exit(1)
        
        # Check if profile file exists - check containers directory first, then main profiles
        containers_profile_path = Path(f"./etc/profiles/containers/{profile}.yml")
        main_profile_path = Path(f"./etc/profiles/servers/{profile}.yml")
        
        profile_path = None
        if containers_profile_path.exists():
            profile_path = containers_profile_path
            console.print(f"[blue]📦 Using container profile: {profile}[/blue]")
        elif main_profile_path.exists():
            profile_path = main_profile_path
            console.print(f"[blue]📋 Using main profile: {profile}[/blue]")
        else:
            console.print(f"[red]Error: Profile '{profile}' not found.[/red]")
            console.print(f"[blue]Searched in:[/blue]")
            console.print(f"  - {containers_profile_path}")
            console.print(f"  - {main_profile_path}")
            console.print("\n[yellow]Available profiles:[/yellow]")
            list_available_profiles(containers_only=False, verbose=False)
            raise typer.Exit(1)
        
        console.print(f"[blue]Deploying containers on target: {target}[/blue]")
        console.print(f"[blue]Using profile: {profile}[/blue]")
        console.print(f"[blue]Inventory: {inventory}[/blue]")
        
        # Load profile configuration
        with open(profile_path, 'r') as f:
            profile_config = yaml.safe_load(f)
        
        # Load host variables if they exist
        host_vars = load_host_variables(target)
        if host_vars:
            console.print(f"[green]✓ Loaded host variables from etc/ansible/host_vars/{target}.yml[/green]")
        
        # Merge configurations
        merged_config = merge_configurations(profile_config, host_vars)
        
        # Check for container definitions
        containers = merged_config.get('containers', {})
        if not containers:
            console.print("[red]Error: No container definitions found in profile or host variables.[/red]")
            console.print("[yellow]Hint: Add 'containers:' section to your profile or host_vars file.[/yellow]")
            raise typer.Exit(1)
        
        # Display deployment information
        display_deployment_info(profile, profile_config, containers)
        
        if dry_run:
            console.print("\n[yellow]🔍 Dry run mode - showing what would be deployed:[/yellow]")
            # Pass merged variables for template resolution
            variables = merged_config.get('vars', {})
            display_container_details(containers, variables)
            console.print("\n[yellow]No changes were made (dry run mode)[/yellow]")
            return
        
        # Create and run Docker deployment playbook
        create_and_run_docker_playbook(target, merged_config, inventory, verbose)
        
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        raise typer.Exit(1)

@docker_app.command("list")
def list_containers(
    target: str = typer.Argument(..., help="Target server to list containers from"),
    inventory: Optional[str] = typer.Option(None, "--inventory", "-i", help="Path to Ansible inventory file"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output")
):
    """
    List running Docker containers on target server.
    
    Examples:
    - cstation docker list sg01
    - cstation docker list web01 --verbose
    """
    console.print(f"[blue]Listing containers on: {target}[/blue]")
    # TODO: Implement container listing functionality
    console.print("[yellow]Container listing functionality coming soon![/yellow]")

@docker_app.command("profile")
def list_profiles(
    profile_name: Optional[str] = typer.Argument(None, help="Specific profile name to display details"),
    containers_only: bool = typer.Option(False, "--containers-only", "-c", help="Show only container profiles"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output")
):
    """
    List available Docker container profiles or show details of a specific profile.
    
    Examples:
    - cstation docker profile
    - cstation docker profile portainer
    - cstation docker profile --containers-only
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
    from rich.table import Table
    
    profiles_dir = Path("./etc/profiles/servers")
    containers_dir = Path("./etc/profiles/containers")
    
    console.print("\n[bold blue]📋 Available Docker Profiles[/bold blue]")
    
    # Create table for profiles
    table = Table(title="Docker Container Profiles")
    table.add_column("Profile", style="cyan")
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
                profiles_found = True
                table.add_row(
                    profile_name,
                    location,
                    f"Error reading: {str(e)}",
                    "?"
                )
    
    # Check main profiles directory if not containers-only
    if not containers_only and profiles_dir.exists():
        for profile_file in profiles_dir.glob("*.yml"):
            # Skip if it's in containers subdirectory
            if profile_file.parent.name == "containers":
                continue
                
            profile_name = profile_file.stem
            location = "profiles/"
            
            # Load profile to check if it has containers
            try:
                with open(profile_file, 'r') as f:
                    profile_data = yaml.safe_load(f) or {}
                description = profile_data.get('description', 'No description')
                containers = profile_data.get('containers', {})
                container_count = len(containers)
                
                # Only show if it has containers or if verbose
                if container_count > 0 or verbose:
                    profiles_found = True
                    table.add_row(
                        profile_name,
                        location,
                        description,
                        str(container_count)
                    )
            except Exception as e:
                if verbose:
                    profiles_found = True
                    table.add_row(
                        profile_name,
                        location,
                        f"Error reading: {str(e)}",
                        "?"
                    )
    
    if profiles_found:
        console.print(table)
        console.print(f"\n[blue]💡 Use 'cstation docker profile <profile_name>' to see details[/blue]")
    else:
        console.print("[yellow]No container profiles found.[/yellow]")
        console.print(f"[blue]💡 Create profiles in {containers_dir}[/blue]")

def show_profile_details(profile_name: str, verbose: bool):
    """
    Show detailed information about a specific profile.
    """
    from rich.table import Table
    from rich.panel import Panel
    
    # Look for profile in containers directory first, then main profiles
    containers_path = Path(f"./etc/profiles/containers/{profile_name}.yml")
    main_path = Path(f"./etc/profiles/servers/{profile_name}.yml")
    
    profile_path = None
    if containers_path.exists():
        profile_path = containers_path
        location = "containers/"
    elif main_path.exists():
        profile_path = main_path
        location = "profiles/"
    else:
        console.print(f"[red]Profile '{profile_name}' not found.[/red]")
        console.print("[blue]Available profiles:[/blue]")
        list_available_profiles(containers_only=False, verbose=False)
        raise typer.Exit(1)
    
    try:
        with open(profile_path, 'r') as f:
            profile_data = yaml.safe_load(f) or {}
        
        # Display profile header
        description = profile_data.get('description', 'No description available')
        console.print(f"\n[bold blue]📋 Profile: {profile_name}[/bold blue]")
        console.print(f"[blue]📍 Location: {location}{profile_name}.yml[/blue]")
        console.print(Panel(description, title="Description", border_style="blue"))
        
        # Display containers
        containers = profile_data.get('containers', {})
        if containers:
            console.print(f"\n[bold green]🐳 Containers ({len(containers)})[/bold green]")
            
            for container_name, container_config in containers.items():
                console.print(f"\n[cyan]• {container_name}[/cyan]")
                
                # Basic info
                image = container_config.get('image', 'Not specified')
                console.print(f"  Image: {image}")
                
                restart_policy = container_config.get('restart_policy', 'unless-stopped')
                console.print(f"  Restart: {restart_policy}")
                
                # Ports
                ports = container_config.get('ports', [])
                if ports:
                    console.print(f"  Ports: {', '.join(ports)}")
                
                # Networks
                networks = container_config.get('networks', [])
                if networks:
                    console.print(f"  Networks: {', '.join(networks)}")
                
                # Volumes
                volumes = container_config.get('volumes', [])
                if volumes:
                    console.print(f"  Volumes: {len(volumes)} mounted")
                    if verbose:
                        for volume in volumes:
                            console.print(f"    - {volume}")
                
                # Environment variables
                env = container_config.get('environment', {})
                if env:
                    console.print(f"  Environment: {len(env)} variables")
                    if verbose:
                        for key, value in env.items():
                            console.print(f"    - {key}={value}")
                
                # Resource limits
                if 'resource_limits' in container_config:
                    limits = container_config['resource_limits']
                    console.print(f"  Resource Limits:")
                    if 'cpu' in limits:
                        console.print(f"    - CPU: {limits['cpu']}")
                    if 'memory' in limits:
                        console.print(f"    - Memory: {limits['memory']}")
        else:
            console.print("\n[yellow]No containers defined in this profile.[/yellow]")
        
        # Show other sections if verbose
        if verbose:
            other_sections = {k: v for k, v in profile_data.items() 
                            if k not in ['description', 'containers']}
            if other_sections:
                console.print(f"\n[bold yellow]📄 Other Sections[/bold yellow]")
                for section, data in other_sections.items():
                    console.print(f"  {section}: {type(data).__name__}")
        
        console.print(f"\n[blue]💡 Deploy with: cstation docker deploy <target> --profile {profile_name}[/blue]")
        
    except Exception as e:
        console.print(f"[red]Error reading profile '{profile_name}': {str(e)}[/red]")
        raise typer.Exit(1)

@docker_app.callback()
def docker_callback(ctx: typer.Context):
    """Docker container management"""
    if ctx.invoked_subcommand is None:
        # Show help when no subcommand is provided
        console.print(ctx.get_help())
        raise typer.Exit(0)

def load_host_variables(target: str) -> dict:
    """
    Load host-specific variables from host_vars directory.
    """
    host_vars_path = Path(f"./etc/ansible/host_vars/{target}.yml")
    if host_vars_path.exists():
        with open(host_vars_path, 'r') as f:
            return yaml.safe_load(f) or {}
    return {}

def merge_configurations(profile_config: dict, host_vars: dict) -> dict:
    """
    Merge profile configuration with host-specific variables.
    Host variables take precedence over profile variables.
    """
    merged_config = profile_config.copy()
    
    # Merge containers configuration if present in host_vars
    if 'containers' in host_vars:
        console.print("[blue]📦 Found container configurations in host variables[/blue]")
        merged_config['containers'] = host_vars['containers']
    
    # Extract Docker daemon configuration variables
    if 'docker_daemon_config' in host_vars:
        console.print("[blue]🐳 Found Docker daemon configuration in host variables[/blue]")
        docker_config = host_vars['docker_daemon_config']
        
        # Extract log options and make them available as top-level variables
        if 'log_opts' in docker_config:
            log_opts = docker_config['log_opts']
            if 'docker_log_max_size' in log_opts:
                merged_config.setdefault('vars', {})['docker_log_max_size'] = log_opts['docker_log_max_size']
            if 'docker_log_max_file' in log_opts:
                merged_config.setdefault('vars', {})['docker_log_max_file'] = log_opts['docker_log_max_file']
        
        # Make other docker daemon config available
        merged_config.setdefault('vars', {})['docker_daemon_config'] = docker_config
    
    # Merge any other host variables into vars section
    if 'vars' not in merged_config:
        merged_config['vars'] = {}
    
    # Add all host variables to the vars section for template access
    for key, value in host_vars.items():
        if key not in ['containers', 'docker_daemon_config']:
            merged_config['vars'][key] = value
    
    return merged_config

def display_deployment_info(profile: str, profile_config: dict, containers: dict):
    """
    Display deployment information in a formatted way.
    """
    description = profile_config.get('description', 'No description available')
    
    console.print(f"\n[bold blue]🐳 Docker Deployment: {profile}[/bold blue]")
    console.print(f"[blue]📝 Description: {description}[/blue]")
    console.print(f"[blue]🐳 Containers to deploy: {len(containers)}[/blue]")
    
    for container_name, container_config in containers.items():
        image = container_config.get('image', 'Unknown')
        ports = container_config.get('ports', [])
        networks = container_config.get('networks', [])
        restart_policy = container_config.get('restart_policy', 'no')
        
        console.print(f"  • {container_name} ({image})")
        if ports:
            ports_str = ', '.join(ports)
            console.print(f"    Ports: {ports_str}")
        if networks:
            networks_str = ', '.join(networks)
            console.print(f"    Networks: {networks_str}")
        console.print(f"    Restart: {restart_policy}")

def resolve_template_variables(text: str, variables: dict) -> str:
    """
    Resolve Jinja2 template variables in text using provided variables.
    """
    from jinja2 import Template, Environment
    
    try:
        # Create Jinja2 environment and template
        env = Environment()
        template = env.from_string(str(text))
        return template.render(**variables)
    except Exception:
        # If template resolution fails, return original text
        return str(text)

def display_container_details(containers: dict, variables: dict = None):
    """
    Display detailed container configuration for dry run.
    """
    if variables is None:
        variables = {}
    
    table = Table(title="Container Deployment Plan")
    table.add_column("Container", style="cyan")
    table.add_column("Image", style="green")
    table.add_column("Ports", style="yellow")
    table.add_column("Networks", style="blue")
    table.add_column("Restart Policy", style="magenta")
    
    for container_name, container_config in containers.items():
        image = container_config.get('image', 'Unknown')
        ports = container_config.get('ports', [])
        networks = container_config.get('networks', [])
        restart_policy = container_config.get('restart_policy', 'no')
        
        # Resolve template variables
        resolved_image = resolve_template_variables(image, variables)
        resolved_ports = [resolve_template_variables(port, variables) for port in ports]
        resolved_networks = [resolve_template_variables(network, variables) for network in networks]
        resolved_restart_policy = resolve_template_variables(restart_policy, variables)
        
        ports_str = ', '.join(resolved_ports)
        networks_str = ', '.join(resolved_networks)
        
        table.add_row(container_name, resolved_image, ports_str, networks_str, resolved_restart_policy)
    
    console.print(table)

def create_and_run_docker_playbook(target: str, merged_config: dict, inventory: str, verbose: bool):
    """
    Create and execute Ansible playbook for Docker container deployment only.
    """
    console.print("\n[blue]Creating Docker deployment playbook...[/blue]")
    
    # Create playbook content
    playbook = {
        'hosts': target,
        'become': True,
        'vars': merged_config.get('vars', {}),
        'tasks': []
    }
    
    # Add container deployment tasks
    containers = merged_config.get('containers', {})
    if containers:
        console.print("[blue]🐳 Adding container deployment tasks[/blue]")
        
        # Create Docker networks first
        networks = set()
        for container_name, container_config in containers.items():
            container_networks = container_config.get('networks', [])
            networks.update(container_networks)
        
        for network in networks:
            if network and network != 'default':
                playbook['tasks'].append({
                    'name': f'Create Docker network {network}',
                    'docker_network': {
                        'name': network,
                        'state': 'present'
                    }
                })
        
        # Deploy containers
        for container_name, container_config in containers.items():
            task_config = {
                'name': f'Deploy container {container_name}',
                'docker_container': {
                    'name': container_config.get('name', container_name),
                    'image': container_config.get('image'),
                    'state': 'started',
                    'restart_policy': container_config.get('restart_policy', 'unless-stopped')
                }
            }
            
            # Add ports if specified
            if 'ports' in container_config:
                task_config['docker_container']['ports'] = container_config['ports']
            
            # Add volumes if specified
            if 'volumes' in container_config:
                task_config['docker_container']['volumes'] = container_config['volumes']
            
            # Add environment variables if specified
            if 'environment' in container_config:
                task_config['docker_container']['env'] = container_config['environment']
            
            # Add networks if specified
            if 'networks' in container_config:
                task_config['docker_container']['networks'] = [{'name': net} for net in container_config['networks']]
            
            # Add resource limits if specified
            if 'resource_limits' in container_config:
                limits = container_config['resource_limits']
                if 'cpu' in limits:
                    # Convert CPU limit to quota (cpu * 100000 microseconds)
                    cpu_quota = int(float(limits['cpu']) * 100000)
                    task_config['docker_container']['cpu_quota'] = cpu_quota
                if 'memory' in limits:
                    task_config['docker_container']['memory'] = limits['memory']
            
            # Add deploy section resource limits if specified
            if 'deploy' in container_config and 'resources' in container_config['deploy']:
                resources = container_config['deploy']['resources']
                if 'limits' in resources:
                    limits = resources['limits']
                    if 'cpus' in limits:
                        # Convert CPU limit to quota (cpus * 100000)
                        cpu_quota = int(float(limits['cpus']) * 100000)
                        task_config['docker_container']['cpu_quota'] = cpu_quota
                    if 'memory' in limits:
                        task_config['docker_container']['memory'] = limits['memory']
            
            playbook['tasks'].append(task_config)
    
    # Write playbook to temporary file
    playbook_content = [playbook]
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        yaml.dump(playbook_content, f, default_flow_style=False)
        playbook_path = f.name
    
    try:
        console.print("[blue]Executing Docker deployment playbook...[/blue]")
        
        # Build ansible-playbook command
        cmd = [
            'ansible-playbook',
            '-i', inventory,
            playbook_path
        ]
        
        if verbose:
            cmd.append('-v')
        
        # Execute the playbook
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Track output for error reporting
        output_lines = []
        error_output = []
        current_task = None
        
        # Process output line by line
        for line in process.stdout:
            line = line.rstrip()
            output_lines.append(line)
            
            # Track current task
            if 'TASK [' in line:
                current_task = line.split('[')[1].split(']')[0]
                console.print(f"[blue]▶ {target}[/blue]")
                console.print(f"  • {current_task}")
            
            # Track errors
            if any(keyword in line.lower() for keyword in ['error', 'failed', 'fatal']):
                error_output.append(line)
            
            # Show task completion status
            if verbose:
                console.print(f"[dim]{line}[/dim]")
            else:
                # Show summary for each host
                if current_task and ('ok=' in line or 'changed=' in line or 'failed=' in line):
                    if 'failed=0' in line and 'unreachable=0' in line:
                        console.print(f"    [green]✓ Completed[/green]")
                    elif 'failed=' in line and not 'failed=0' in line:
                        console.print(f"    [red]✗ Failed[/red]")
                    elif 'changed=' in line and not 'changed=0' in line:
                        console.print(f"    [green]✓ Changed[/green]")
                    else:
                        console.print(f"    [green]✓ OK[/green]")
        
        process.wait()
        
        console.print("\n[bold]📊 Execution Summary[/bold]")
        if process.returncode == 0:
            console.print("    [green]✓ Completed[/green]")
            console.print("\n[green]✓ Docker deployment completed successfully![/green]")
        else:
            console.print("    [red]✗ Failed[/red]")
            console.print("\n[red]✗ Docker deployment failed![/red]")
            console.print("\n[bold]Error details:[/bold]")
            for line in error_output[-10:]:  # Show last 10 lines for context
                if 'FAILED' in line or 'ERROR' in line or 'fatal:' in line:
                    console.print(f"[red]{line}[/red]")
            raise typer.Exit(1)
    
    finally:
        # Clean up temporary file
        try:
            os.unlink(playbook_path)
        except OSError:
            pass