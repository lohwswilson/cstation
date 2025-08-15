import typer
from typing import Optional
from rich.console import Console
from rich.table import Table
from pathlib import Path
import yaml
import subprocess
import tempfile
import os

console = Console()

def setup_software(
    target: str = typer.Argument(..., help="Target server or 'all' for all servers"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Software profile to install (e.g., database_server, odoo_app)"),
    inventory: Optional[str] = typer.Option(None, "--inventory", "-i", help="Path to Ansible inventory file"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be installed without executing"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output")
):
    """
    Setup software packages on servers using Ansible profiles (excludes containers).
    
    Examples:
    - cstation server setup sg01 --profile database_server
    - cstation server setup all --profile odoo_app --dry-run
    
    Note: For container deployment, use 'cstation docker deploy' command.
    """
    try:
        # Set default inventory path
        if not inventory:
            inventory = "/etc/cstation/ansible/inventory/hosts.yml"
        
        # Validate inventory file exists
        if not Path(inventory).exists():
            console.print(f"[red]Error: Inventory file not found: {inventory}[/red]")
            raise typer.Exit(1)
        
        # Validate profile is provided
        if not profile:
            console.print("[red]Error: Profile is required. Use --profile to specify a software profile.[/red]")
            raise typer.Exit(1)
        
        # Check if profile file exists
        profile_path = Path(f"/etc/cstation/profiles/servers/{profile}.yml")
        if not profile_path.exists():
            console.print(f"[red]Error: Profile file not found: {profile_path}[/red]")
            console.print("[yellow]Available profiles:[/yellow]")
            from ..profiles import list_profiles
            list_profiles()
            raise typer.Exit(1)
        
        # Load and validate profile
        try:
            with open(profile_path, 'r') as f:
                profile_config = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            console.print(f"[red]Error parsing profile file {profile_path}: {e}[/red]")
            raise typer.Exit(1)
        
        # Display what will be installed
        console.print(f"[blue]Setting up software on target: {target}[/blue]")
        console.print(f"[blue]Using profile: {profile}[/blue]")
        console.print(f"[blue]Inventory: {inventory}[/blue]")
        
        if dry_run:
            console.print("\n[yellow]DRY RUN - No changes will be made[/yellow]")
        
        # Load host-specific variables
        host_vars = load_host_variables(target)
        
        # Merge profile config with host variables
        merged_config = merge_configurations(profile_config, host_vars)
        
        # Show profile contents
        display_profile_info(merged_config, profile)
        
        if dry_run:
            console.print("\n[green]Dry run completed. Use without --dry-run to execute.[/green]")
            return
        
        # Create and execute Ansible playbook (excluding containers)
        create_and_run_software_playbook(target, merged_config, inventory, verbose)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)





def display_profile_info(merged_config: dict, profile_name: str):
    """
    Display information about the profile to be installed.
    """
    console.print(f"\n[green]📋 Profile:[/green] {profile_name}")
    
    description = merged_config.get('description', 'No description available')
    console.print(f"[blue]📝 Description:[/blue] {description}")
    
    packages = merged_config.get('packages', [])
    if packages:
        package_count = len(packages)
        console.print(f"[yellow]📦 Packages to install:[/yellow] {package_count}")
        for pkg in packages[:3]:  # Show first 3 packages
            if isinstance(pkg, dict):
                name = pkg.get('name', 'Unknown')
                version = pkg.get('version', 'latest')
                console.print(f"  • {name} ({version})")
            else:
                console.print(f"  • {pkg}")
        if package_count > 3:
            console.print(f"  ... and {package_count - 3} more")
    
    services = merged_config.get('services', [])
    if services:
        service_count = len(services)
        console.print(f"[cyan]⚙️  Services to configure:[/cyan] {service_count}")
        for service in services[:3]:  # Show first 3 services
            if isinstance(service, dict):
                name = service.get('name', 'Unknown')
                enabled = service.get('enabled', True)
                status = "enabled" if enabled else "disabled"
                console.print(f"  • {name} ({status})")
            else:
                console.print(f"  • {service}")
        if service_count > 3:
            console.print(f"  ... and {service_count - 3} more")
    
    containers = merged_config.get('containers', {})
    if containers:
        container_count = len(containers)
        console.print(f"[magenta]🐳 Containers to deploy:[/magenta] {container_count}")
        for container_name, container_config in list(containers.items())[:3]:  # Show first 3 containers
            image = container_config.get('image', 'Unknown')
            console.print(f"  • {container_name} ({image})")
        if container_count > 3:
            console.print(f"  ... and {container_count - 3} more")



def load_host_variables(target: str) -> dict:
    """
    Load host-specific variables from host_vars directory.
    """
    host_vars = {}
    host_vars_file = Path(f"/etc/cstation/ansible/host_vars/{target}.yml")
    
    if host_vars_file.exists():
        try:
            with open(host_vars_file, 'r') as f:
                host_vars = yaml.safe_load(f) or {}
            console.print(f"[green]✓ Loaded host variables from {host_vars_file}[/green]")
        except yaml.YAMLError as e:
            console.print(f"[yellow]Warning: Error loading host variables from {host_vars_file}: {e}[/yellow]")
    else:
        console.print(f"[yellow]Info: No host variables file found for {target}[/yellow]")
    
    return host_vars

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
    
    # Merge other host-specific overrides
    for key in ['packages', 'services', 'configurations']:
        if key in host_vars:
            console.print(f"[blue]🔧 Overriding {key} with host-specific values[/blue]")
            merged_config[key] = host_vars[key]
    
    
    # Merge any other host variables into vars section
    if 'vars' not in merged_config:
        merged_config['vars'] = {}
    
    # Add all host variables to the vars section for template access
    for key, value in host_vars.items():
        if key not in ['containers', 'packages', 'services', 'configurations']:
            merged_config['vars'][key] = value
    
    return merged_config

def create_and_run_software_playbook(target: str, merged_config: dict, inventory: str, verbose: bool):
    """
    Create and execute Ansible playbook for software installation (excludes containers).
    """
    console.print("\n[blue]Creating Ansible playbook...[/blue]")
    
    # Create playbook content
    playbook = {
        'hosts': target,
        'become': True,
        'vars': merged_config.get('vars', {}),
        'tasks': []
    }
    
    # Add package installation tasks
    packages = merged_config.get('packages', [])
    if packages:
        package_names = []
        for pkg in packages:
            if isinstance(pkg, dict):
                name = pkg.get('name')
                if name:
                    package_names.append(name)
            else:
                package_names.append(str(pkg))
        
        if package_names:
            playbook['tasks'].append({
                'name': 'Install packages',
                'apt': {
                    'name': package_names,
                    'state': 'present',
                    'update_cache': True
                }
            })
    
    # Add service management tasks
    services = merged_config.get('services', [])
    for service in services:
        if isinstance(service, dict):
            name = service.get('name')
            enabled = service.get('enabled', True)
            state = service.get('state', 'started')
            
            if name:
                playbook['tasks'].append({
                    'name': f'Configure service {name}',
                    'systemd': {
                        'name': name,
                        'enabled': enabled,
                        'state': state
                    }
                })
        else:
            playbook['tasks'].append({
                'name': f'Configure service {service}',
                'systemd': {
                    'name': str(service),
                    'enabled': True,
                    'state': 'started'
                }
            })
    
    # Note: Container deployment is handled by 'cstation docker deploy'
    # This function only handles software packages, services, and configurations
    
    # Add copy tasks
    copy_tasks = merged_config.get('copy', [])
    for copy_task in copy_tasks:
        if isinstance(copy_task, dict):
            dest = copy_task.get('dest')
            content = copy_task.get('content')
            
            if dest and content:
                # Create directory for destination if needed
                dest_dir = os.path.dirname(dest)
                if dest_dir and dest_dir != '/':
                    playbook['tasks'].append({
                        'name': f'Create directory {dest_dir}',
                        'file': {
                            'path': dest_dir,
                            'state': 'directory',
                            'mode': '0755'
                        }
                    })
                
                playbook['tasks'].append({
                    'name': f'Copy content to {dest}',
                    'copy': {
                        'content': content,
                        'dest': dest,
                        'mode': copy_task.get('mode', '0644')
                    }
                })
    
    # Add configuration file tasks
    configs = merged_config.get('configurations', [])
    for config in configs:
        if isinstance(config, dict):
            src = config.get('src')
            dest = config.get('dest')
            if src and dest:
                # Convert relative template path to absolute path
                template_path = Path('/etc/cstation/ansible/templates') / src
                
                # Ensure destination directory exists
                dest_dir = str(Path(dest).parent)
                playbook['tasks'].append({
                    'name': f'Create directory for {dest}',
                    'file': {
                        'path': dest_dir,
                        'state': 'directory',
                        'mode': '0755'
                    }
                })
                
                playbook['tasks'].append({
                    'name': f'Copy configuration file to {dest}',
                    'template': {
                        'src': str(template_path.absolute()),
                        'dest': dest,
                        'backup': True
                    }
                })
    
    # Add post-installation tasks
    post_install_tasks = merged_config.get('post_install_tasks', [])
    for task in post_install_tasks:
        if isinstance(task, dict):
            playbook['tasks'].append(task)
    
    # Add handlers
    handlers = merged_config.get('handlers', [])
    if handlers:
        playbook['handlers'] = handlers
    
    # Write playbook to temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        yaml.dump([playbook], f, default_flow_style=False)
        playbook_path = f.name
    
    try:
        # Run ansible-playbook
        console.print(f"[blue]Executing Ansible playbook...[/blue]")
        
        cmd = [
            'ansible-playbook',
            '-i', inventory,
            playbook_path
        ]
        
        if verbose:
            cmd.append('-v')
        
        # Change to project root directory to ensure ansible.cfg and templates are found
        project_root = Path.cwd()
        
        # Set environment to use our ansible.cfg
        env = os.environ.copy()
        env['ANSIBLE_CONFIG'] = '/etc/cstation/ansible/ansible.cfg'
        
        if verbose:
            # Run with full output for verbose mode
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root, env=env)
            
            if result.returncode == 0:
                console.print("[green]✓ Software setup completed successfully![/green]")
                console.print("\n[bold]Ansible output:[/bold]")
                console.print(result.stdout)
            else:
                console.print("[red]✗ Software setup failed![/red]")
                console.print(f"[red]Error: {result.stderr}[/red]")
                console.print("\n[bold]Ansible output:[/bold]")
                console.print(result.stdout)
                raise typer.Exit(1)
        else:
            # Run with real-time progress display for non-verbose mode
            import re
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                     text=True, cwd=project_root, env=env, bufsize=1, universal_newlines=True)
            
            task_pattern = re.compile(r'^TASK \[(.+?)\]')
            play_pattern = re.compile(r'^PLAY \[(.+?)\]')
            recap_pattern = re.compile(r'^PLAY RECAP')
            
            current_task = None
            error_output = []
            
            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue
                    
                # Capture all output for error reporting
                error_output.append(line)
                
                # Match PLAY lines
                play_match = play_pattern.match(line)
                if play_match:
                    play_name = play_match.group(1)
                    console.print(f"[cyan]▶ {play_name}[/cyan]")
                    continue
                
                # Match TASK lines
                task_match = task_pattern.match(line)
                if task_match:
                    current_task = task_match.group(1)
                    console.print(f"  [yellow]• {current_task}[/yellow]")
                    continue
                
                # Match PLAY RECAP
                if recap_pattern.match(line):
                    console.print(f"[blue]📊 Execution Summary[/blue]")
                    continue
                
                # Show host results (ok, changed, failed, etc.)
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
            
            if process.returncode == 0:
                console.print("\n[green]✓ Software setup completed successfully![/green]")
            else:
                console.print("\n[red]✗ Software setup failed![/red]")
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