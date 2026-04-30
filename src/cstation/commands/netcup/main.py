#!/usr/bin/env python3
"""
Netcup SCP authentication commands for CStation CLI
"""

from __future__ import annotations

import typer
from rich import print as rprint
from rich.console import Console

from cstation.providers.netcup_auth import (
    NetcupAuthError,
    credentials_exist,
    delete_credentials,
    get_access_token,
    load_credentials,
    request_device_code,
    revoke_refresh_token,
    save_credentials,
    wait_for_device_authorization,
    CREDENTIALS_FILE,
)

console = Console()

netcup_app = typer.Typer(
    name="netcup",
    help="Netcup SCP provider management",
    invoke_without_command=True,
)


@netcup_app.command("auth-login")
def auth_login() -> None:
    """Authenticate with Netcup SCP via OAuth2 device-code flow."""
    console.print("[bold]Netcup SCP OAuth2 Authentication[/bold]")
    console.print()

    try:
        device_response = request_device_code()
    except NetcupAuthError as e:
        console.print(f"[red]✗[/red] Failed to request device code: {e}")
        raise typer.Exit(1)

    verification_uri = device_response.get("verification_uri_complete") or device_response.get("verification_uri", "")
    user_code = device_response.get("user_code", "")
    device_code = device_response.get("device_code", "")
    expires_in = device_response.get("expires_in", 600)
    interval = device_response.get("interval", 5)

    if not device_code:
        console.print("[red]✗[/red] No device_code in response")
        raise typer.Exit(1)

    console.print("1. Open the following URL in your browser:")
    console.print(f"   [bold blue]{verification_uri}[/bold blue]")
    console.print()
    if user_code:
        console.print("2. Enter the code: [bold green]{user_code}[/bold green]" if "{user_code}" in "{user_code}" else f"2. Enter the code: [bold green]{user_code}[/bold green]")
        console.print()
    console.print("Waiting for authorization...")

    try:
        token_response = wait_for_device_authorization(
            device_code, interval=interval, expires_in=expires_in,
        )
    except NetcupAuthError as e:
        console.print(f"[red]✗[/red] Authorization failed: {e}")
        raise typer.Exit(1)

    refresh_token = token_response.get("refresh_token")
    if not refresh_token:
        console.print("[red]✗[/red] No refresh_token in response")
        raise typer.Exit(1)

    save_credentials(refresh_token)
    console.print()
    console.print(f"[green]✓[/green] Authenticated successfully!")
    console.print(f"  Credentials saved to: {CREDENTIALS_FILE}")


@netcup_app.command("auth-logout")
def auth_logout() -> None:
    """Remove stored Netcup SCP credentials."""
    if not credentials_exist():
        console.print("[yellow]No stored credentials found.[/yellow]")
        raise typer.Exit(0)

    try:
        creds = load_credentials()
        refresh_token = creds.get("refresh_token", "")
        if refresh_token:
            revoke_refresh_token(refresh_token)
    except NetcupAuthError:
        pass

    delete_credentials()
    console.print("[green]✓[/green] Credentials removed.")


@netcup_app.command("auth-show")
def auth_show() -> None:
    """Show Netcup SCP authentication status."""
    console.print(f"Credentials file: {CREDENTIALS_FILE}")
    if credentials_exist():
        console.print("[green]✓[/green] Credentials file exists")
        try:
            creds = load_credentials()
            console.print(f"  Refresh token present: {'yes' if creds.get('refresh_token') else 'no'}")
            console.print("  Testing access token...")
            token = get_access_token()
            console.print(f"[green]✓[/green] Access token obtained (length: {len(token)})")
        except NetcupAuthError as e:
            console.print(f"[red]✗[/red] Error: {e}")
    else:
        console.print("[red]✗[/red] No credentials found")
        console.print("  Run [bold]cstation netcup auth-login[/bold] to authenticate")


@netcup_app.callback()
def netcup_callback(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        rprint(ctx.get_help())
        raise typer.Exit(0)