#!/usr/bin/env python3
"""
Profile command module for CStation CLI
"""

import typer
from rich import print as rprint

# Import subcommands
from .docker import list_docker_profiles, push_docker

# Server functionality has been moved to main server module

# Create Docker sub-app
docker_app = typer.Typer(
    name="docker",
    help="Docker service management",
    invoke_without_command=True
)

# Add commands to the docker app
docker_app.command("ls")(list_docker_profiles)
docker_app.command("push")(push_docker)

@docker_app.callback()
def docker_callback(ctx: typer.Context):
    """Docker service management"""
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

# Add sub-apps to the main service app
service_app.add_typer(docker_app, name="docker")

@service_app.callback()
def service_callback(ctx: typer.Context):
    """Software service management"""
    if ctx.invoked_subcommand is None:
        # Show help when no subcommand is provided
        rprint(ctx.get_help())
        raise typer.Exit(0)