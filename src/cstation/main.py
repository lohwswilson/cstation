#!/usr/bin/env python3
"""
CStation - Infrastructure Management CLI
A DevOps CLI tool for managing infrastructure using Ansible
"""

import typer
from rich import print as rprint

# Import configuration management
from .config import initialize_configuration, get_config

# Import command modules
from .commands.version.main import version
from .commands.server.main import server_app
from .commands.github.main import github_app
from .commands.docker.main import docker_app
from .commands.vps.main import vps_app
from .commands.netcup.main import netcup_app
from .commands.cloudflare.main import cloudflare_app


def version_callback(value: bool):
    if value:
        from .commands.version.main import version
        version()
        raise typer.Exit()


# Initialize main Typer app
app = typer.Typer(
    name="cstation",
    help="Infrastructure Management CLI for DevOps",
    add_completion=False,
    invoke_without_command=True
)

# Add commands to the main app
app.command()(version)
app.add_typer(server_app)
app.add_typer(github_app)
app.add_typer(docker_app)
app.add_typer(vps_app, name="vps")
app.add_typer(netcup_app)
app.add_typer(cloudflare_app)


@app.callback()
def main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(None, "--version", callback=version_callback, is_eager=True),
):
    """Infrastructure Management CLI for DevOps"""
    # Initialize configuration on first run
    config_manager = get_config()
    
    if ctx.invoked_subcommand is None:
        # Show help when no subcommand is provided
        rprint(ctx.get_help())
        raise typer.Exit(0)


def main():
    """Main entry point for the CLI application"""
    # Initialize configuration
    initialize_configuration()
    app()


if __name__ == "__main__":
    main()
