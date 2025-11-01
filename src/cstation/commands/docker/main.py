#!/usr/bin/env python3
"""
Docker command module for CStation CLI
"""

import typer
from rich import print as rprint

# Import subcommands
from .playbook import playbook_app


# Create Docker app
docker_app = typer.Typer(
    name="docker", 
    help="Docker infrastructure management", 
    invoke_without_command=True
)

# Add commands to the app
docker_app.add_typer(playbook_app, name="playbook")


@docker_app.callback()
def docker_callback(ctx: typer.Context):
    """Docker infrastructure management"""
    if ctx.invoked_subcommand is None:
        # Show help when no subcommand is provided
        rprint(ctx.get_help())
        raise typer.Exit(0)