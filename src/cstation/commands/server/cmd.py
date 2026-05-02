#!/usr/bin/env python3
"""
Server command execution module
"""

import typer
from rich.console import Console
from ...inventory import get_inventory
from ...ssh import SSHManager

console = Console()

# Create command app
cmd_app = typer.Typer(
    name="cmd",
    help="Remote command execution",
    invoke_without_command=True
)

def run_remote_command(
    hostname: str = typer.Argument(..., help="Target host to run the command on"),
    command: str = typer.Argument(..., help="Command to execute"),
    sudo: bool = typer.Option(False, "--sudo", "-s", help="Run with sudo"),
    inventory_path: Optional[str] = typer.Option(None, "-i", "--inventory", help="Inventory file path")
):
    """
    Execute a command on a specific target host via SSH.
    """
    inventory = get_inventory(inventory_path)
    if not inventory.host_exists(hostname):
        console.print(f"[red]Host '{hostname}' not found in inventory[/red]")
        raise typer.Exit(1)
        
    host_info = inventory.get_host_info(hostname)
    remote_host = host_info.get('ansible_host', host_info.get('host', hostname))
    remote_user = host_info.get('ansible_user', host_info.get('user', 'root'))
    
    console.print(f"[yellow]Running command on {hostname} ({remote_user}@{remote_host})...[/yellow]")
    
    ssh = SSHManager(host=remote_host, user=remote_user)
    result = ssh.run(command, hide=False, sudo=sudo)
    
    if result and result.ok:
        console.print(f"[green]✓ Command executed successfully[/green]")
    else:
        console.print(f"[red]Command failed[/red]")
        raise typer.Exit(1)

cmd_app.command("run")(run_remote_command)

@cmd_app.callback()
def cmd_callback(ctx: typer.Context):
    """Remote command execution"""
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
