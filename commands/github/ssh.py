#!/usr/bin/env python3
"""
GitHub SSH key management for remote servers
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

def setup_github_ssh(
    hostname: str = typer.Argument(..., help="Target hostname from inventory"),
    inventory: Optional[str] = typer.Option(
        "etc/ansible/inventory/hosts.yml", 
        "-i", "--inventory", 
        help="Inventory file path"
    ),
    key_path: Optional[str] = typer.Option(
        None,
        "-k", "--key-path",
        help="Path to SSH private key for GitHub (default: ~/.ssh/id_rsa)"
    ),
    github_user: Optional[str] = typer.Option(
        None,
        "-u", "--github-user",
        help="GitHub username (will prompt if not provided)"
    ),
    generate_key: bool = typer.Option(
        False,
        "--generate",
        help="Generate new SSH key pair for GitHub if not exists"
    ),
    add_to_github: bool = typer.Option(
        False,
        "--add-to-github",
        help="Display instructions to add public key to GitHub"
    )
):
    """
    Setup SSH key for GitHub access on remote servers using Ansible
    """
    
    # Default SSH key path
    if key_path is None:
        key_path = os.path.expanduser("~/.ssh/id_rsa")
    
    public_key_path = f"{key_path}.pub"
    
    # Get GitHub username if not provided
    if github_user is None:
        github_user = Prompt.ask("Enter your GitHub username")
    
    # Check if SSH key exists
    if not os.path.exists(key_path) or not os.path.exists(public_key_path):
        if generate_key:
            console.print(f"[yellow]Generating new SSH key pair for GitHub...[/yellow]")
            
            # Generate SSH key with GitHub email
            email = Prompt.ask("Enter email for SSH key", default=f"{github_user}@users.noreply.github.com")
            try:
                subprocess.run([
                    "ssh-keygen", 
                    "-t", "ed25519", 
                    "-C", email,
                    "-f", key_path,
                    "-N", ""
                ], check=True)
                console.print(f"[green]SSH key generated: {key_path}[/green]")
            except subprocess.CalledProcessError as e:
                console.print(f"[red]Failed to generate SSH key: {e}[/red]")
                raise typer.Exit(1)
        else:
            console.print(f"[red]SSH key not found: {key_path}[/red]")
            console.print(f"[yellow]Use --generate to create a new key pair[/yellow]")
            raise typer.Exit(1)
    
    # Read the private and public keys
    try:
        with open(key_path, 'r') as f:
            private_key = f.read().strip()
        with open(public_key_path, 'r') as f:
            public_key = f.read().strip()
    except Exception as e:
        console.print(f"[red]Failed to read SSH keys: {e}[/red]")
        raise typer.Exit(1)
    
    # Check if inventory file exists
    if not os.path.exists(inventory):
        console.print(f"[red]Inventory file not found: {inventory}[/red]")
        raise typer.Exit(1)
    
    console.print(Panel.fit(
        f"[bold]Setting up GitHub SSH access for host: {hostname}[/bold]\n"
        f"GitHub User: {github_user}\n"
        f"Key: {key_path}\n"
        f"Inventory: {inventory}",
        title="GitHub SSH Setup",
        border_style="blue"
    ))
    
    # Show public key for GitHub if requested
    if add_to_github:
        console.print("\n[yellow]Add this public key to your GitHub account:[/yellow]")
        console.print(Panel.fit(
            public_key,
            title="Public Key for GitHub",
            border_style="green"
        ))
        console.print(f"\n[blue]Go to: https://github.com/settings/ssh/new[/blue]")
        console.print(f"[blue]Title: {hostname}-github-key[/blue]")
        
        if not Confirm.ask("Have you added the public key to GitHub?"):
            console.print("[yellow]Please add the public key to GitHub first, then run this command again.[/yellow]")
            raise typer.Exit(0)
    
    # Confirm before proceeding
    if not Confirm.ask("Proceed with GitHub SSH setup on remote server?"):
        console.print("[yellow]Operation cancelled[/yellow]")
        raise typer.Exit(0)
    
    # Create temporary ansible playbook for GitHub SSH setup
    playbook_content = f"""
---
- name: Setup GitHub SSH Access
  hosts: {hostname}
  gather_facts: no
  vars:
    github_user: "{github_user}"
    ssh_key_path: "/home/{{{{ ansible_user | default('root') }}}}/.ssh/github_rsa"
  tasks:
    - name: Ensure .ssh directory exists
      file:
        path: "/home/{{{{ ansible_user | default('root') }}}}/.ssh"
        state: directory
        mode: '0700'
        owner: "{{{{ ansible_user | default('root') }}}}"
      become: yes
    
    - name: Copy GitHub SSH private key
      copy:
        content: |
{chr(10).join('          ' + line for line in private_key.split(chr(10)))}
        dest: "{{{{ ssh_key_path }}}}"
        mode: '0600'
        owner: "{{{{ ansible_user | default('root') }}}}"
      become: yes
    
    - name: Copy GitHub SSH public key
      copy:
        content: "{public_key}"
        dest: "{{{{ ssh_key_path }}}}.pub"
        mode: '0644'
        owner: "{{{{ ansible_user | default('root') }}}}"
      become: yes
    
    - name: Add GitHub to known_hosts
      known_hosts:
        name: github.com
        key: "github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl"
        path: "/home/{{{{ ansible_user | default('root') }}}}/.ssh/known_hosts"
      become: yes
    
    - name: Create SSH config for GitHub
      blockinfile:
        path: "/home/{{{{ ansible_user | default('root') }}}}/.ssh/config"
        create: yes
        mode: '0600'
        owner: "{{{{ ansible_user | default('root') }}}}"
        marker: "# {{{{ ansible_managed }}}} - GitHub SSH Config"
        block: |
          Host github.com
              HostName github.com
              User git
              IdentityFile {{{{ ssh_key_path }}}}
              IdentitiesOnly yes
      become: yes
    
    - name: Test GitHub SSH connection
      command: ssh -T git@github.com
      register: github_test
      failed_when: github_test.rc not in [0, 1]
      changed_when: false
      become: yes
      become_user: "{{{{ ansible_user | default('root') }}}}"
    
    - name: Display GitHub connection result
      debug:
        msg: "{{{{ github_test.stderr }}}}"
"""
    
    # Write temporary playbook
    temp_playbook = "/tmp/github_ssh_setup.yml"
    try:
        with open(temp_playbook, 'w') as f:
            f.write(playbook_content)
    except Exception as e:
        console.print(f"[red]Failed to create temporary playbook: {e}[/red]")
        raise typer.Exit(1)
    
    # Run ansible playbook
    console.print("[yellow]Running Ansible playbook for GitHub SSH setup...[/yellow]")
    try:
        cmd = [
            "ansible-playbook",
            "-i", inventory,
            temp_playbook,
            "-v"
        ]
        
        # Set environment to use our ansible.cfg
        env = os.environ.copy()
        env['ANSIBLE_CONFIG'] = str(Path.cwd() / 'etc/ansible/ansible.cfg')
        
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        
        if result.returncode == 0:
            console.print("[green]GitHub SSH setup completed successfully![/green]")
            console.print("\n[bold]You can now clone repositories using:[/bold]")
            console.print(f"git clone git@github.com:{github_user}/repository.git")
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
    
    console.print("\n[green]GitHub SSH setup process completed![/green]")
    console.print(f"\n[blue]Next steps:[/blue]")
    console.print(f"1. SSH to {hostname}")
    console.print(f"2. Test GitHub access: ssh -T git@github.com")
    console.print(f"3. Clone repositories: git clone git@github.com:{github_user}/repo.git")