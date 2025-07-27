#!/usr/bin/env python3
"""
Server command module for CStation CLI
"""

import typer
from rich import print as rprint

# Import subcommands
from .ssh import setup_ssh
from .status import server_status, server_uptime
from .list import server_list

# Create Server app
server_app = typer.Typer(
    name="server", 
    help="Remote server management", 
    invoke_without_command=True
)

# Add commands to the app
server_app.command("ssh")(setup_ssh)
server_app.command("status")(server_status)
server_app.command("uptime")(server_uptime)
server_app.command("list")(server_list)

@server_app.callback()
def server_callback(ctx: typer.Context):
    """Remote server management"""
    if ctx.invoked_subcommand is None:
        # Show help when no subcommand is provided
        rprint(ctx.get_help())
        raise typer.Exit(0)