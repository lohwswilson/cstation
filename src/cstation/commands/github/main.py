#!/usr/bin/env python3
"""
GitHub command module for CStation CLI
"""

import typer
from rich import print as rprint

# Import subcommands
from .ssh import setup_github_ssh
from .repo import repo_app

# Create GitHub app
github_app = typer.Typer(
    name="github", help="GitHub integration & OCA/Odoo module repository management", invoke_without_command=True
)

# Add commands to the app
github_app.command("ssh")(setup_github_ssh)
github_app.add_typer(repo_app, name="repo")


@github_app.callback()
def github_callback(ctx: typer.Context):
    """GitHub repository, OCA module update/sync, and SSH key management"""
    if ctx.invoked_subcommand is None:
        # Show help when no subcommand is provided
        rprint(ctx.get_help())
        raise typer.Exit(0)
