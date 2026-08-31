#!/usr/bin/env python3
"""
CStation - Infrastructure Management CLI
A DevOps CLI tool for managing infrastructure using Ansible
"""

import click
import typer
from rich import print as rprint

# Import configuration management
from .config import config_manager, initialize_configuration

from .commands.version.main import version
from .commands.github.main import github_app
from .commands.docker.main import docker_app
from .commands.vps.main import vps_app
from .commands.dns.main import dns_app
from .commands.cloudflare.main import cloudflare_app
from .commands.odoo.main import odoo_app
from .commands.image.main import image_app
from .commands.server.main import server_app
from .commands.lint.main import lint_app
from .commands.completion.main import completion_app


def version_callback(value: bool):
    if value:
        from .commands.version.main import version
        version()
        raise typer.Exit()


# Initialize main Typer app
app = typer.Typer(
    name="cstation",
    help="Infrastructure Management CLI for DevOps",
    invoke_without_command=True
)

# Add commands to the main app
app.command()(version)
app.add_typer(github_app)
app.add_typer(docker_app)
app.add_typer(vps_app, name="vps")
app.add_typer(dns_app)
app.add_typer(cloudflare_app, hidden=True)  # legacy alias for dns
app.add_typer(odoo_app)
app.add_typer(image_app)
app.add_typer(server_app)
app.add_typer(lint_app)
app.add_typer(lint_app, name="check", hidden=True)
app.add_typer(completion_app)


@app.callback()
def main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(None, "--version", callback=version_callback, is_eager=True),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show configuration loading details"),
):
    """Infrastructure Management CLI for DevOps"""
    if ctx.invoked_subcommand is None:
        # Show help when no subcommand is provided
        rprint(ctx.get_help())
        raise typer.Exit(0)

    # Initialize configuration (quiet unless --verbose)
    initialize_configuration(verbose=verbose)


def main():
    """Main entry point for the CLI application"""
    try:
        app()
    except (typer.Exit, click.Abort):
        # Normal CLI control flow — let Click handle exit codes.
        raise
    except Exception as e:
        if config_manager.verbose:
            # --verbose: surface the full traceback for debugging.
            raise
        rprint(f"[red]✗[/red] {e}")
        raise typer.Exit(1)


if __name__ == "__main__":
    main()
