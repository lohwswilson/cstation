#!/usr/bin/env python3
"""
Docker playbook management commands
"""

import typer
from rich.console import Console
from rich.table import Table
from pathlib import Path
import subprocess
import os
import yaml

console = Console()

# Create playbook app
playbook_app = typer.Typer(
    name="playbook",
    help="Docker Ansible playbook management",
    invoke_without_command=True
)

def get_playbook_dir():
    """Get the docker playbooks directory path"""
    # Try to find docker playbooks directory - prioritize system location first
    current_dir = Path.cwd()
    playbook_paths = [
        Path("/etc/ansible/playbooks/docker"),               # System-wide ansible playbooks
        Path("/etc/ansible/playbooks"),                      # System-wide ansible playbooks root
        Path("/etc/cstation/ansible/playbooks/docker"),     # Fallback to old path
        Path("/etc/cstation/ansible/playbooks"),            # Fallback to old path root
        current_dir / "playbooks" / "docker",
        current_dir / "playbooks",
        Path(__file__).parent.parent.parent.parent.parent / "playbooks" / "docker",
    ]
    
    for path in playbook_paths:
        if path.exists():
            return path
    
    # Default to system location
    return Path("/etc/ansible/playbooks/docker")

def list_docker_playbooks():
    """
    List available Docker Ansible playbooks.
    """
    playbooks_dir = get_playbook_dir()
    
    if not playbooks_dir.exists():
        console.print(f"[red]Docker playbooks directory not found: {playbooks_dir}[/red]")
        console.print(f"[yellow]Searched in: {playbooks_dir}[/yellow]")
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
            description = "Docker playbook"
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

def push_playbook(
    ansible_playbook: str = typer.Argument(..., help="Name of the Docker Ansible playbook to execute"),
    target_host: str = typer.Argument(..., help="Target host to run the playbook on"),
    ask_pass: bool = typer.Option(False, "--ask-pass", help="Ask for SSH password authentication"),
    config: str = typer.Option(None, "--config", "-c", help="Path to YAML configuration file with extra variables for the playbook (searches in /etc/cstation/ansible/containers first for relative paths)")
):
    """
    Execute a Docker Ansible playbook on a specific target host.
    
    The --config option allows you to specify a YAML file containing extra variables
    that will be passed to the ansible-playbook command using --extra-vars.
    """
    # Validate config file if provided
    config_path = None
    if config:
        config_path = Path(config)
        if not config_path.is_absolute():
            # For relative paths, prioritize system-wide ansible containers directory
            containers_dirs = [
                Path("/etc/ansible/containers"),                 # System-wide ansible containers
                Path("/etc/cstation/ansible/containers")        # Fallback to old path
            ]
            
            config_path_found = False
            for containers_dir in containers_dirs:
                containers_config_path = containers_dir / config_path
                if containers_config_path.exists():
                    config_path = containers_config_path
                    config_path_found = True
                    break
            
            if not config_path_found:
                # Fallback to current working directory
                config_path = Path.cwd() / config_path
        
        # Check if config file exists
        if not config_path.exists():
            console.print(f"[red]Config file not found: {config_path}[/red]")
            if not Path(config).is_absolute():
                console.print(f"[yellow]Searched in:[/yellow]")
                console.print(f"  - {Path('/etc/ansible/containers') / config}")
                console.print(f"  - {Path('/etc/cstation/ansible/containers') / config}")
                console.print(f"  - {Path.cwd() / config}")
            raise typer.Exit(1)
        
        # Validate YAML syntax
        try:
            with open(config_path, 'r') as f:
                config_data = yaml.safe_load(f)
                if config_data is None:
                    console.print(f"[red]Config file is empty or contains no valid YAML data: {config_path}[/red]")
                    raise typer.Exit(1)
                if not isinstance(config_data, dict):
                    console.print(f"[red]Config file must contain a YAML dictionary/object: {config_path}[/red]")
                    raise typer.Exit(1)
        except yaml.YAMLError as e:
            console.print(f"[red]Invalid YAML syntax in config file {config_path}:[/red]")
            console.print(f"[red]{str(e)}[/red]")
            raise typer.Exit(1)
        except Exception as e:
            console.print(f"[red]Error reading config file {config_path}: {str(e)}[/red]")
            raise typer.Exit(1)
        
        console.print(f"[green]✓ Config file validated: {config_path}[/green]")
    
    # Check if target host exists in inventory
    from ..server.inventory_utils import get_host_info
    
    host_info = get_host_info(target_host)
    if not host_info:
        console.print(f"[red]Host '{target_host}' not found in inventory[/red]")
        raise typer.Exit(1)
    
    # Automatically append .yml extension if not provided
    if not ansible_playbook.endswith(('.yml', '.yaml')):
        ansible_playbook = f"{ansible_playbook}.yml"
    
    # Check if playbook exists in docker playbook directory
    playbooks_dir = get_playbook_dir()
    playbook_path = playbooks_dir / ansible_playbook
    
    if not playbook_path.exists():
        console.print(f"[red]Docker Ansible playbook not found: {playbook_path}[/red]")
        # List available playbooks
        available_playbooks = list(playbooks_dir.glob("*.yml")) + list(playbooks_dir.glob("*.yaml"))
        if available_playbooks:
            console.print("[yellow]Available Docker playbooks:[/yellow]")
            for pb in available_playbooks:
                console.print(f"  - {pb.stem}")
        raise typer.Exit(1)
    
    # Determine inventory path - prioritize system location
    inventory_paths = [
        Path("/etc/ansible/inventory/production/hosts.yml"),  # New hierarchical structure
        Path("/etc/ansible/inventory"),                       # System-wide inventory directory
        Path("/etc/ansible/inventory/hosts.yml"),            # Alternative system location
        Path("/etc/cstation/ansible/inventory"),             # Fallback to old path
        Path("/etc/cstation/ansible/inventory/hosts.yml"),
        Path("/etc/cstation/ansible/inventory/hosts"),
        playbooks_dir / "inventory" / "hosts.yml",
        playbooks_dir / "inventory" / "hosts",
        playbooks_dir / "inventory.yml"
    ]
    
    inventory_path = None
    for inv_path in inventory_paths:
        if inv_path.exists():
            inventory_path = str(inv_path)
            break
    
    if not inventory_path:
        console.print("[red]No inventory file found[/red]")
        console.print("[yellow]Searched in:[/yellow]")
        for inv_path in inventory_paths:
            console.print(f"  - {inv_path}")
        raise typer.Exit(1)
    
    try:
        # Run ansible playbook
        config_info = f" with config file '{config_path}'" if config_path else ""
        console.print(f"[yellow]Running Docker playbook '{ansible_playbook}' on {target_host}{config_info}...[/yellow]")
        
        cmd = [
            "ansible-playbook",
            str(playbook_path),
            "-i", inventory_path,
            "--limit", target_host,
            "-e", f"target_host={target_host}",
            "-v"
        ]
        
        # Add config file as extra vars if provided
        if config_path:
            cmd.extend(["--extra-vars", f"@{config_path}"])
        
        # Add password authentication if requested
        if ask_pass:
            cmd.append("--ask-pass")
        
        # Set environment to use ansible.cfg from system location first
        env = os.environ.copy()
        ansible_cfg_paths = [
            Path("/etc/ansible/ansible.cfg"),                   # System-wide ansible config
            Path("/etc/cstation/ansible/ansible.cfg"),         # Fallback to old path
            playbooks_dir / "ansible.cfg"
        ]
        
        ansible_cfg_path = None
        for cfg_path in ansible_cfg_paths:
            if cfg_path.exists():
                ansible_cfg_path = str(cfg_path)
                break
        
        if ansible_cfg_path:
            env['ANSIBLE_CONFIG'] = ansible_cfg_path
        
        result = subprocess.run(cmd, env=env, cwd=str(playbooks_dir))
        
        if result.returncode == 0:
            console.print(f"[green]✓ Successfully executed Docker playbook '{ansible_playbook}' on {target_host}[/green]")
        else:
            console.print(f"[red]Docker Ansible playbook failed with exit code {result.returncode}[/red]")
            raise typer.Exit(result.returncode)
            
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Failed to run Docker ansible playbook: {e}[/red]")
        raise typer.Exit(1)
    except FileNotFoundError:
        console.print(f"[red]ansible-playbook command not found. Please install Ansible.[/red]")
        raise typer.Exit(1)

# Add commands to the playbook app
playbook_app.command("list", help="List available Docker Ansible playbooks")(list_docker_playbooks)
playbook_app.command("push", help="Execute a Docker Ansible playbook on a target host")(push_playbook)

@playbook_app.callback()
def playbook_callback(ctx: typer.Context):
    """Docker Ansible playbook management"""
    if ctx.invoked_subcommand is None:
        # Default to list when no subcommand is provided
        list_docker_playbooks()

# Keep the original function name for backward compatibility
list_docker_code = list_docker_playbooks