"""
TUI command module for CStation CLI
"""
from __future__ import annotations

import typer
from rich.console import Console

console = Console()

tui_app = typer.Typer(
    name="tui",
    help="Interactive TUI dashboard with live VPS & container monitoring",
    invoke_without_command=True,
)


def run_tui() -> None:
    """Launch the interactive CStation TUI dashboard."""
    try:
        from .app import CStationApp
        app = CStationApp()
        app.run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to start TUI dashboard: {e}")
        raise typer.Exit(1)


@tui_app.callback()
def tui_callback(ctx: typer.Context) -> None:
    """Interactive TUI dashboard with live VPS & container monitoring."""
    if ctx.invoked_subcommand is None:
        run_tui()
