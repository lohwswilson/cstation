"""
Main Sync Command Module

Provides sync operations for various applications including PerfectWork.
"""

import typer
from rich.console import Console

# Import PW sync functionality
from ..pw.main import pw_app

console = Console()

# Create the main sync app
sync_app = typer.Typer(
    name="sync",
    help="Sync operations for various applications",
    rich_markup_mode="rich"
)

# Add PW as a subcommand
sync_app.add_typer(pw_app, name="pw", help="PerfectWork sync operations")

@sync_app.callback()
def sync_callback():
    """
    Sync operations for various applications.
    
    Available applications:
    - pw: PerfectWork sync operations
    
    Examples:
        cstation sync pw sg07-db 18.0 --port 8288
        cstation sync pw production-server 18.0 --dry-run
    """
    pass