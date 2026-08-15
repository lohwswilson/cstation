#!/usr/bin/env python3
"""
Provider authentication commands for CStation CLI
"""

from __future__ import annotations

import typer
from rich import print as rprint
from ..netcup.main import (
    auth_login as netcup_login,
    auth_logout as netcup_logout,
    auth_show as netcup_show,
)

auth_app = typer.Typer(
    name="auth",
    help="Provider authentication management",
    invoke_without_command=True,
)

netcup_auth_app = typer.Typer(
    name="netcup",
    help="Netcup SCP OAuth2 authentication",
    invoke_without_command=True,
)

netcup_auth_app.command("login")(netcup_login)
netcup_auth_app.command("logout")(netcup_logout)
netcup_auth_app.command("status")(netcup_show)
netcup_auth_app.command("show")(netcup_show)


@netcup_auth_app.callback()
def netcup_auth_callback(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        rprint(ctx.get_help())
        raise typer.Exit(0)


auth_app.add_typer(netcup_auth_app, name="netcup")


@auth_app.callback()
def auth_callback(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        rprint(ctx.get_help())
        raise typer.Exit(0)
