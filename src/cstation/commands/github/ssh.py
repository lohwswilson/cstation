#!/usr/bin/env python3
"""
GitHub SSH key management for remote servers
"""

import os
import subprocess
import typer
import base64
from pathlib import Path
from typing import Optional
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from cstation.ssh import SSHManager
from cstation.commands.vps.main import _resolve_vps_dir, _load_vps_config, _ssh_from_config

console = Console()

def setup_github_ssh(
    target: str = typer.Argument(..., help="VPS name (e.g. sg01.synercatalyst.com)"),
    key_path: Optional[str] = typer.Option(
        None,
        "-k", "--key-path",
        help="Path to local SSH private key for GitHub (default: ~/.ssh/id_rsa)"
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
    Setup SSH key for GitHub access on a remote VPS.
    """
    # 1. Resolve VPS and build SSH manager
    vps_dir = _resolve_vps_dir(Path(target))
    vps_data = _load_vps_config(vps_dir)
    ssh = _ssh_from_config(vps_data)

    # Default SSH key path
    if key_path is None:
        key_path = os.path.expanduser("~/.ssh/id_rsa")

    public_key_path = f"{key_path}.pub"

    # Get GitHub username if not provided
    if github_user is None:
        github_user = Prompt.ask("Enter your GitHub username")

    # Check if local SSH key exists
    if not os.path.exists(key_path) or not os.path.exists(public_key_path):
        if generate_key:
            console.print(f"[yellow]Generating new SSH key pair for GitHub...[/yellow]")
            email = Prompt.ask("Enter email for SSH key", default=f"{github_user}@users.noreply.github.com")
            try:
                subprocess.run([
                    "ssh-keygen", "-t", "ed25519", "-C", email, "-f", key_path, "-N", ""
                ], check=True)
                console.print(f"[green]SSH key generated: {key_path}[/green]")
            except subprocess.CalledProcessError as e:
                console.print(f"[red]Failed to generate SSH key: {e}[/red]")
                raise typer.Exit(1)
        else:
            console.print(f"[red]Local SSH key not found: {key_path}[/red]")
            console.print(f"[yellow]Use --generate to create a new key pair[/yellow]")
            raise typer.Exit(1)

    # Read the keys
    try:
        with open(key_path, 'r') as f:
            private_key = f.read().strip()
        with open(public_key_path, 'r') as f:
            public_key = f.read().strip()
    except Exception as e:
        console.print(f"[red]Failed to read SSH keys: {e}[/red]")
        raise typer.Exit(1)

    console.print(Panel.fit(
        f"[bold]Setting up GitHub SSH access for VPS: {vps_data.identity.name}[/bold]\n"
        f"GitHub User: {github_user}\n"
        f"Host: {ssh.host}\n"
        f"Local Key: {key_path}",
        title="GitHub SSH Setup",
        border_style="blue"
    ))

    if add_to_github:
        console.print("\n[yellow]Add this public key to your GitHub account:[/yellow]")
        console.print(Panel.fit(public_key, title="Public Key for GitHub", border_style="green"))
        console.print(f"\n[blue]Go to: https://github.com/settings/ssh/new[/blue]")
        if not Confirm.ask("Have you added the public key to GitHub?"):
            console.print("[yellow]Please add the public key to GitHub first, then run this command again.[/yellow]")
            raise typer.Exit(0)

    if not Confirm.ask("Proceed with remote VPS setup?"):
        console.print("[yellow]Operation cancelled[/yellow]")
        raise typer.Exit(0)

    # 2. Remote Setup via SSHManager
    remote_ssh_dir = "~/.ssh"
    remote_key_path = "~/.ssh/github_rsa"

    console.print("[yellow]Performing remote setup...[/yellow]")

    # Ensure .ssh exists
    ssh.run(f"mkdir -p {remote_ssh_dir} && chmod 700 {remote_ssh_dir}", sudo=False)

    # Copy private key
    encoded_private = base64.b64encode(private_key.encode()).decode()
    ssh.run(f"echo '{encoded_private}' | base64 -d > {remote_key_path} && chmod 600 {remote_key_path}", sudo=False)

    # Copy public key
    ssh.run(f"echo '{public_key}' > {remote_key_path}.pub && chmod 644 {remote_key_path}.pub", sudo=False)

    # Add GitHub to known_hosts
    github_key = "github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl"
    ssh.run(f"grep -q 'github.com' {remote_ssh_dir}/known_hosts 2>/dev/null || echo '{github_key}' >> {remote_ssh_dir}/known_hosts", sudo=False)

    # Configure SSH config
    ssh_config_block = f"""
Host github.com
    HostName github.com
    User git
    IdentityFile {remote_key_path}
    IdentitiesOnly yes
"""
    encoded_config = base64.b64encode(ssh_config_block.encode()).decode()
    ssh.run(f"echo '{encoded_config}' | base64 -d >> {remote_ssh_dir}/config && chmod 600 {remote_ssh_dir}/config", sudo=False)

    # Test connection
    console.print("[yellow]Testing GitHub SSH connection...[/yellow]")
    result = ssh.run("ssh -T git@github.com", hide=True, sudo=False)
    # ssh -T git@github.com returns 1 on success for some reason, but prints a welcome message
    stderr = getattr(result, "stderr", "")
    if "Hi" in stderr or "successfully authenticated" in stderr:
        console.print("[green]✓ GitHub SSH setup completed successfully![/green]")
    else:
        console.print(f"[red]✗ Connection test failed:[/red]\n{stderr}")
        raise typer.Exit(1)

    console.print(f"\n[blue]You can now clone repositories on {vps_data.identity.name} using:[/blue]")
    console.print(f"git clone git@github.com:{github_user}/repository.git")