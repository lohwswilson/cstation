#!/usr/bin/env python3
"""
SSH key management for remote servers
"""

import os
import subprocess
import typer
from pathlib import Path
from typing import Optional
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

console = Console()

def setup_ssh(
    hostname: str = typer.Argument(..., help="Target hostname from inventory"),
    inventory: Optional[str] = typer.Option(
        "etc/ansible/inventory/hosts.yml", 
        "-i", "--inventory", 
        help="Inventory file path"
    ),
    key_path: Optional[str] = typer.Option(
        None,
        "-k", "--key-path",
        help="Path to SSH public key (default: ~/.ssh/id_rsa.pub)"
    ),
    generate_key: bool = typer.Option(
        False,
        "--generate",
        help="Generate new SSH key pair if not exists"
    )
):
    """
    Setup SSH key authentication for a remote server using Ansible
    """
    
    # Default SSH key path
    if key_path is None:
        key_path = os.path.expanduser("~/.ssh/id_rsa.pub")
    
    # Check if SSH key exists
    if not os.path.exists(key_path):
        if generate_key:
            private_key_path = key_path.replace(".pub", "")
            if not os.path.exists(private_key_path):
                console.print(f"[yellow]Generating new SSH key pair...[/yellow]")
                
                # Generate SSH key
                email = Prompt.ask("Enter email for SSH key", default="user@example.com")
                try:
                    subprocess.run([
                        "ssh-keygen", 
                        "-t", "rsa", 
                        "-b", "4096", 
                        "-C", email,
                        "-f", private_key_path,
                        "-N", ""
                    ], check=True)
                    console.print(f"[green]SSH key generated: {private_key_path}[/green]")
                except subprocess.CalledProcessError as e:
                    console.print(f"[red]Failed to generate SSH key: {e}[/red]")
                    raise typer.Exit(1)
        else:
            console.print(f"[red]SSH public key not found: {key_path}[/red]")
            console.print(f"[yellow]Use --generate to create a new key pair[/yellow]")
            raise typer.Exit(1)
    
    # Read the public key
    try:
        with open(key_path, 'r') as f:
            public_key = f.read().strip()
    except Exception as e:
        console.print(f"[red]Failed to read SSH public key: {e}[/red]")
        raise typer.Exit(1)
    
    # Check if inventory file exists
    if not os.path.exists(inventory):
        console.print(f"[red]Inventory file not found: {inventory}[/red]")
        raise typer.Exit(1)
    
    console.print(Panel.fit(
        f"[bold]Setting up SSH key for host: {hostname}[/bold]\n"
        f"Key: {key_path}\n"
        f"Inventory: {inventory}",
        title="SSH Key Setup",
        border_style="blue"
    ))
    
    # Confirm before proceeding
    if not Confirm.ask("Proceed with SSH key setup?"):
        console.print("[yellow]Operation cancelled[/yellow]")
        raise typer.Exit(0)
    
    # Create temporary ansible playbook for SSH key setup
    playbook_content = f"""
---
- name: Setup SSH Key Authentication
  hosts: {hostname}
  gather_facts: no
  tasks:
    - name: Ensure .ssh directory exists
      file:
        path: ~/.ssh
        state: directory
        mode: '0700'
      become: yes
      become_user: "{{{{ ansible_user | default('root') }}}}"
    
    - name: Add SSH public key to authorized_keys
      authorized_key:
        user: "{{{{ ansible_user | default('root') }}}}"
        key: "{public_key}"
        state: present
      become: yes
    
    - name: Test SSH connection
      ping:
"""
    
    # Write temporary playbook
    temp_playbook = "/tmp/ssh_setup.yml"
    try:
        with open(temp_playbook, 'w') as f:
            f.write(playbook_content)
    except Exception as e:
        console.print(f"[red]Failed to create temporary playbook: {e}[/red]")
        raise typer.Exit(1)
    
    # Run ansible playbook
    console.print("[yellow]Running Ansible playbook...[/yellow]")
    try:
        cmd = [
            "ansible-playbook",
            "-i", inventory,
            temp_playbook,
            "-v"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            console.print("[green]SSH key setup completed successfully![/green]")
            console.print("\n[bold]You can now connect using:[/bold]")
            console.print(f"ssh {hostname}")
        else:
            console.print(f"[red]Ansible playbook failed:[/red]")
            console.print(result.stderr)
            raise typer.Exit(1)
            
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Failed to run ansible playbook: {e}[/red]")
        raise typer.Exit(1)
    except FileNotFoundError:
        console.print(f"[red]ansible-playbook command not found. Please install Ansible.[/red]")
        raise typer.Exit(1)
    finally:
        # Clean up temporary playbook
        if os.path.exists(temp_playbook):
            os.remove(temp_playbook)
    
    console.print("\n[green]SSH key setup process completed![/green]")