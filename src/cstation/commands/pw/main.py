#!/usr/bin/env python3
"""
PerfectWork (PW) sync commands for CStation CLI

This module provides fast file synchronization operations using direct rsync calls
instead of Ansible for better performance.
"""

import typer
from typing import Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich import print as rprint

from .sync import PWSync
from ...config import get_config

# Initialize Typer app and Rich console
app = typer.Typer(name="pw", help="PerfectWork sync operations", add_completion=False, rich_markup_mode="rich")
console = Console()


@app.command("sync")
def sync_pw_files(
    host: str = typer.Argument(..., help="Target hostname or group (e.g., sg07-db)"),
    version: str = typer.Argument(..., help="PW version (e.g., 3.0, 4.0, 5.0, 18.0)"),
    port: int = typer.Option(22, "--port", "-p", help="SSH port (default: 22, cluster: 8288)"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show what would be synced without executing"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
    exclude_cache: bool = typer.Option(True, "--exclude-cache/--include-cache", help="Exclude __pycache__ directories"),
):
    """
    Sync PerfectWork files to remote server for Docker container access.

    This command prepares and syncs PW and PW_ADDONS files to the target server
    so Docker containers can access them.

    Examples:
        cstation server pw sync sg07-db 3.0 --port 8288
        cstation server pw sync production-server 18.0 --dry-run
        cstation server pw sync dev-server 5.0 --verbose
    """

    # Validate version format (should be numeric)
    try:
        float(version)
    except ValueError:
        rprint(
            f"[red]Error:[/red] Invalid version format '{version}'. Version should be numeric (e.g., 3.0, 4.0, 18.0)"
        )
        raise typer.Exit(1)

    # Show operation summary
    panel_content = f"""
[bold cyan]PerfectWork Sync Operation[/bold cyan]

[bold]Target:[/bold] {host}.ansis.com.sg
[bold]Version:[/bold] PW.{version}
[bold]SSH Port:[/bold] {port}
[bold]Mode:[/bold] {"Dry Run" if dry_run else "Live Sync"}
[bold]Verbose:[/bold] {"Yes" if verbose else "No"}
[bold]Exclude Cache:[/bold] {"Yes" if exclude_cache else "No"}
    """

    console.print(Panel(panel_content, title="Sync Configuration", border_style="blue"))

    if not dry_run:
        confirm = typer.confirm(f"Proceed with syncing PW.{version} to {host}?")
        if not confirm:
            rprint("[yellow]Operation cancelled.[/yellow]")
            raise typer.Exit(0)

    # Initialize sync manager
    config = get_config()
    pw_sync = PWSync(config, console)

    try:
        with Progress(
            SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console, transient=True
        ) as progress:
            # Execute sync operation
            success = pw_sync.sync_files(
                host=host,
                version=version,
                port=port,
                dry_run=dry_run,
                verbose=verbose,
                exclude_cache=exclude_cache,
                progress=progress,
            )

            if success:
                rprint(f"[green]✓[/green] Successfully synced PW.{version} to {host}")
            else:
                rprint(f"[red]✗[/red] Failed to sync PW.{version} to {host}")
                raise typer.Exit(1)

    except KeyboardInterrupt:
        rprint("\n[yellow]Operation cancelled by user.[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        rprint(f"[red]Error:[/red] {str(e)}")
        raise typer.Exit(1)


@app.command("status")
def check_sync_status(
    host: str = typer.Argument(..., help="Target hostname to check"),
    version: str = typer.Argument(..., help="PW version to check"),
    port: int = typer.Option(22, "--port", "-p", help="SSH port"),
):
    """
    Check the sync status of PW files on remote server.
    """
    config = get_config()
    pw_sync = PWSync(config, console)

    try:
        status = pw_sync.check_status(host, version, port)

        if status:
            rprint(f"[green]✓[/green] PW.{version} is available on {host}")
            # Show additional status information
            for key, value in status.items():
                rprint(f"  [cyan]{key}:[/cyan] {value}")
        else:
            rprint(f"[red]✗[/red] PW.{version} not found or inaccessible on {host}")

    except Exception as e:
        rprint(f"[red]Error checking status:[/red] {str(e)}")
        raise typer.Exit(1)


@app.command("clean")
def clean_temp_files(
    version: Optional[str] = typer.Argument(None, help="Specific version to clean (optional)"),
    all_versions: bool = typer.Option(False, "--all", help="Clean all temporary files"),
):
    """
    Clean temporary sync files from local system.
    """
    config = get_config()
    pw_sync = PWSync(config, console)

    try:
        cleaned = pw_sync.clean_temp_files(version, all_versions)

        if cleaned:
            rprint(f"[green]✓[/green] Cleaned {len(cleaned)} temporary files/directories")
            for item in cleaned:
                rprint(f"  [dim]- {item}[/dim]")
        else:
            rprint("[yellow]No temporary files found to clean.[/yellow]")

    except Exception as e:
        rprint(f"[red]Error cleaning files:[/red] {str(e)}")
        raise typer.Exit(1)
