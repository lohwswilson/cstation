#!/usr/bin/env python3
"""
Setup command for CStation CLI
"""

import typer
from pathlib import Path
from rich import print as rprint


def setup(
    force: bool = typer.Option(False, "--force", help="Force overwrite existing configuration")
):
    """Setup local configuration directory structure"""
    etc_path = Path("./etc")
    
    if etc_path.exists() and not force:
        rprint(f"[yellow]Warning:[/yellow] Directory './etc' already exists. Use --force to overwrite.")
        raise typer.Exit(1)
    
    # Create etc directory
    etc_path.mkdir(exist_ok=True)
    rprint(f"[green]✓[/green] Created configuration directory: ./etc")
    
    # Create Ansible configuration structure
    ansible_dirs = [
        "ansible/inventory",
        "ansible/group_vars",
        "ansible/host_vars",
        "ansible/playbooks",
        "ansible/roles"
    ]
    
    for dir_name in ansible_dirs:
        (etc_path / dir_name).mkdir(parents=True, exist_ok=True)
        rprint(f"[green]✓[/green] Created directory: ./etc/{dir_name}")
    
    # Create sample inventory file
    inventory_content = """[webservers]
# web1.example.com
# web2.example.com

[databases]
# db1.example.com

[all:vars]
# ansible_user=ubuntu
# ansible_ssh_private_key_file=~/.ssh/id_rsa
"""
    (etc_path / "ansible" / "inventory" / "hosts.yml").write_text(inventory_content)
    rprint(f"[green]✓[/green] Created sample inventory: ./etc/ansible/inventory/hosts.yml")
    
    # Create configuration README
    readme_content = """# Configuration Directory

This directory contains all configuration files for CStation infrastructure management.

## Structure

### Ansible Configuration
- `ansible/inventory/` - Ansible inventory files
- `ansible/group_vars/` - Group variables
- `ansible/host_vars/` - Host variables  
- `ansible/playbooks/` - Ansible playbooks
- `ansible/roles/` - Ansible roles

## Usage Examples

### Ansible
```bash
# Run playbook with local inventory
cstation ansible playbook ./etc/ansible/playbooks/site.yml -i ./etc/ansible/inventory/hosts.yml

# Ping hosts using local inventory
cstation ansible ping -i ./etc/ansible/inventory/hosts.yml
```
"""
    (etc_path / "README.md").write_text(readme_content)
    rprint(f"[green]✓[/green] Created configuration README: ./etc/README.md")
    
    rprint(f"\n[bold green]Configuration directory './etc' setup successfully![/bold green]")
    rprint(f"[blue]Tip:[/blue] Use './etc/ansible/inventory/hosts.yml' as your default inventory file.")