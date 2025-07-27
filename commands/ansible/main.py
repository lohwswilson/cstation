#!/usr/bin/env python3
"""
Ansible command module for CStation CLI
"""

import typer
from rich import print as rprint

# Import subcommands
from .playbook import run_playbook
from .ping import ansible_ping
from .galaxy import ansible_galaxy
from .config import ansible_config
from .inventory import ansible_inventory

# Create Ansible app
ansible_app = typer.Typer(
    name="ansible", 
    help="Ansible infrastructure management", 
    invoke_without_command=True
)

# Add commands to the app
ansible_app.command("playbook")(run_playbook)
ansible_app.command("ping")(ansible_ping)
ansible_app.command("galaxy")(ansible_galaxy)
ansible_app.command("config")(ansible_config)
ansible_app.command("inventory")(ansible_inventory)

@ansible_app.callback()
def ansible_callback(ctx: typer.Context):
    """Ansible infrastructure management"""
    if ctx.invoked_subcommand is None:
        # Show help when no subcommand is provided
        rprint(ctx.get_help())
        raise typer.Exit(0)