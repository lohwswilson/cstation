#!/usr/bin/env python3
"""
CStation - Infrastructure Management CLI
A DevOps CLI tool for managing infrastructure using Ansible
"""

import typer
from rich import print as rprint

# Import command modules
from commands.version.main import version
from commands.server.main import server_app
from commands.github.main import github_app
from commands.docker.main import docker_app

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

@app.callback()
def main_callback(ctx: typer.Context):
    """Infrastructure Management CLI for DevOps"""
    if ctx.invoked_subcommand is None:
        # Show help when no subcommand is provided
        rprint(ctx.get_help())
        raise typer.Exit(0)


if __name__ == "__main__":
    app()
