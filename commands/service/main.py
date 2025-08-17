#!/usr/bin/env python3
"""
Profile command module for CStation CLI
"""

import typer
from rich import print as rprint

# Import subcommands
from .profiles import list_profiles

# Create Server sub-app
server_app = typer.Typer(
    name="server",
    help="Server service management",
    invoke_without_command=True
)

# Add commands to the server app
server_app.command("ls")(list_profiles)

@server_app.callback()
def server_callback(ctx: typer.Context):
    """Server service management"""
    if ctx.invoked_subcommand is None:
        # Show help when no subcommand is provided
        rprint(ctx.get_help())
        raise typer.Exit(0)

# Create main Service app
service_app = typer.Typer(
    name="service", 
    help="Software service management", 
    invoke_without_command=True
)

# Add server sub-app to the main service app
service_app.add_typer(server_app, name="server")

@service_app.callback()
def service_callback(ctx: typer.Context):
    """Software service management"""
    if ctx.invoked_subcommand is None:
        # Show help when no subcommand is provided
        rprint(ctx.get_help())
        raise typer.Exit(0)