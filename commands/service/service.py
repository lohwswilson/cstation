#!/usr/bin/env python3
"""
List profiles command for server management
"""

import typer
from rich.console import Console
from rich.table import Table
from pathlib import Path
import yaml
import subprocess
import tempfile
import os

console = Console()

def list_service():
    """
    List available Ansible playbooks in the server directory.
    """
    playbooks_dir = Path("/etc/cstation/service/server")
    
    if not playbooks_dir.exists():
        console.print(f"[red]Playbooks directory not found: {playbooks_dir}[/red]")
        return
    
    table = Table(title="Available Server Playbooks")
    table.add_column("Playbook", style="cyan")
    table.add_column("Description", style="green")
    table.add_column("Size", style="yellow")
    table.add_column("Modified", style="magenta")
    
    playbook_files = list(playbooks_dir.glob("*.yml")) + list(playbooks_dir.glob("*.yaml"))
    
    if not playbook_files:
        console.print("[yellow]No playbook files found in the server directory[/yellow]")
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


def push_server(ansible_playbook: str, target_host: str):
    """
    Execute an Ansible playbook on a specific target host.
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
    
    # Check if playbook exists in server directory
    playbook_path = Path(f"/etc/cstation/service/server/{ansible_playbook}")
    if not playbook_path.exists():
        console.print(f"[red]Ansible playbook not found: {playbook_path}[/red]")
        raise typer.Exit(1)
    
    try:
        # Run ansible playbook
        console.print(f"[yellow]Running playbook '{ansible_playbook}' on {target_host}...[/yellow]")
        
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
            console.print(f"[green]✓ Successfully executed playbook '{ansible_playbook}' on {target_host}[/green]")
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


def generate_playbook_from_profile(profile_config: dict, hostname: str) -> str:
    """
    Generate Ansible playbook content from server profile configuration.
    """
    playbook = {
        'name': f'Deploy server configuration to {hostname}',
        'hosts': hostname,
        'become': True,
        'gather_facts': True,
        'tasks': []
    }
    
    # Add package installation tasks
    packages = profile_config.get('packages', [])
    if packages:
        package_names = []
        for pkg in packages:
            if isinstance(pkg, dict):
                package_names.append(pkg.get('name'))
            else:
                package_names.append(str(pkg))
        
        playbook['tasks'].append({
            'name': 'Install required packages',
            'apt': {
                'name': package_names,
                'state': 'present',
                'update_cache': True
            }
        })
    
    # Add service management tasks
    services = profile_config.get('services', [])
    for service in services:
        if isinstance(service, dict):
            service_name = service.get('name')
            enabled = service.get('enabled', True)
            state = service.get('state', 'started')
            
            playbook['tasks'].append({
                'name': f'Manage {service_name} service',
                'systemd': {
                    'name': service_name,
                    'enabled': enabled,
                    'state': state
                }
            })
    
    # Add configuration file tasks
    configurations = profile_config.get('configurations', [])
    for config in configurations:
        if isinstance(config, dict):
            src = config.get('src')
            dest = config.get('dest')
            
            if src and dest:
                playbook['tasks'].append({
                    'name': f'Deploy configuration file {dest}',
                    'template': {
                        'src': f'/etc/cstation/ansible/templates/{src}',
                        'dest': dest,
                        'backup': True
                    },
                    'notify': ['restart docker'] if 'docker' in dest else []
                })
    
    # Add environment variables
    env_vars = profile_config.get('environment_variables', {})
    if env_vars:
        env_content = '\n'.join([f'{key}={value}' for key, value in env_vars.items()])
        playbook['tasks'].append({
            'name': 'Set environment variables',
            'blockinfile': {
                'path': '/etc/environment',
                'block': env_content,
                'marker': '# {mark} CSTATION MANAGED BLOCK'
            }
        })
    
    # Add post-install tasks
    post_tasks = profile_config.get('post_install_tasks', [])
    for task in post_tasks:
        if isinstance(task, dict):
            playbook['tasks'].append(task)
    
    # Add handlers
    handlers = profile_config.get('handlers', [])
    if handlers:
        playbook['handlers'] = handlers
    
    # Convert to YAML
    import yaml
    return yaml.dump([playbook], default_flow_style=False, sort_keys=False)