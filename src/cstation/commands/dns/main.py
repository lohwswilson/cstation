#!/usr/bin/env python3
"""
DNS management commands for CStation CLI
"""

from __future__ import annotations

import typer
from rich import print as rprint
from ..cloudflare.main import (
    list_zones,
    cloudflarePlan as dns_plan,
    cloudflareApply as dns_apply,
)

dns_app = typer.Typer(
    name="dns",
    help="DNS zone and record management (Cloudflare)",
    invoke_without_command=True,
)

dns_app.command("zones", help="List DNS zones")(list_zones)
dns_app.command("plan", help="Dry-run: compare DNS config against the provider and show drift")(dns_plan)
dns_app.command("apply", help="Apply DNS records from ~/.config/cstation/dns/ to the provider")(dns_apply)


@dns_app.callback()
def dns_callback(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        rprint(ctx.get_help())
        raise typer.Exit(0)
