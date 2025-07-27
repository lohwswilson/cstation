#!/usr/bin/env python3
"""
Ansible config command
"""

import typer
import subprocess
from typing import Optional
from pathlib import Path
from rich import print as rprint


def ansible_config(
    action: str = typer.Argument(..., help="Config action (init, view, edit, set, get)"),
    key: Optional[str] = typer.Argument(None, help="Configuration key (for get/set actions)"),
    value: Optional[str] = typer.Argument(None, help="Configuration value (for set action)"),
    config_file: Optional[str] = typer.Option("./etc/ansible/ansible.cfg", "-c", "--config", help="Config file path"),
    global_config: bool = typer.Option(False, "--global", help="Use global ansible.cfg")
):
    """Manage Ansible configuration (ansible.cfg)"""
    config_path = Path(config_file) if not global_config else Path.home() / ".ansible.cfg"
    
    if action == "init":
        # Create default ansible.cfg
        config_content = """[defaults]
host_key_checking = False
inventory = ./etc/ansible/inventory/hosts.yml
roles_path = ./etc/ansible/roles
retry_files_enabled = False
stdout_callback = yaml
bin_ansible_callbacks = True

[inventory]
enable_plugins = host_list, script, auto, yaml, ini, toml

[ssh_connection]
ssh_args = -o ControlMaster=auto -o ControlPersist=60s
pipelining = True
"""
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(config_content)
        rprint(f"[green]✓[/green] Created Ansible config: {config_path}")
        
    elif action == "view":
        if config_path.exists():
            rprint(f"[blue]Ansible configuration ({config_path}):[/blue]")
            rprint(config_path.read_text())
        else:
            rprint(f"[yellow]Warning:[/yellow] Config file {config_path} does not exist")
            
    elif action == "edit":
        if not config_path.exists():
            rprint(f"[yellow]Warning:[/yellow] Config file {config_path} does not exist. Creating...")
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.touch()
        
        import os
        editor = os.environ.get('EDITOR', 'vim')
        try:
            subprocess.run([editor, str(config_path)], check=True)
            rprint(f"[green]✓[/green] Config file edited: {config_path}")
        except subprocess.CalledProcessError:
            rprint(f"[red]✗[/red] Failed to open editor for {config_path}")
            
    elif action == "set":
        if not key or not value:
            rprint(f"[red]Error:[/red] Both key and value are required for 'set' action")
            raise typer.Exit(1)
            
        # Simple key=value setting (basic implementation)
        if not config_path.exists():
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text("[defaults]\n")
            
        content = config_path.read_text()
        lines = content.split('\n')
        
        # Find and update or add the key
        updated = False
        for i, line in enumerate(lines):
            if line.strip().startswith(f"{key} ="):
                lines[i] = f"{key} = {value}"
                updated = True
                break
                
        if not updated:
            # Add to [defaults] section
            for i, line in enumerate(lines):
                if line.strip() == "[defaults]":
                    lines.insert(i + 1, f"{key} = {value}")
                    updated = True
                    break
                    
        if not updated:
            lines.extend(["[defaults]", f"{key} = {value}"])
            
        config_path.write_text('\n'.join(lines))
        rprint(f"[green]✓[/green] Set {key} = {value} in {config_path}")
        
    elif action == "get":
        if not key:
            rprint(f"[red]Error:[/red] Key is required for 'get' action")
            raise typer.Exit(1)
            
        if config_path.exists():
            content = config_path.read_text()
            for line in content.split('\n'):
                if line.strip().startswith(f"{key} ="):
                    value = line.split('=', 1)[1].strip()
                    rprint(f"[blue]{key}:[/blue] {value}")
                    return
            rprint(f"[yellow]Warning:[/yellow] Key '{key}' not found in {config_path}")
        else:
            rprint(f"[yellow]Warning:[/yellow] Config file {config_path} does not exist")
    else:
        rprint(f"[red]Error:[/red] Unknown action '{action}'. Use: init, view, edit, set, get")
        raise typer.Exit(1)