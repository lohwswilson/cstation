"""
Config command module for CStation CLI:
Handles configuration export, import, inspection, and migration.
"""
from __future__ import annotations

import os
import shutil
import tarfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from cstation.config import CSTATION_CONFIG_DIR
from cstation.state import record_audit

console = Console()

config_app = typer.Typer(
    name="config",
    help="Manage CStation configuration: export, import, inspect",
    invoke_without_command=True,
)

IGNORED_PATTERNS = {
    ".DS_Store",
    "state.db",
    "state.db-wal",
    "state.db-shm",
}

SECRET_PATTERNS = {
    ".env",
    "netcup-oauth.json",
}


def _is_ignored(path: Path) -> bool:
    """Check if file should be ignored during export."""
    name = path.name
    if name in IGNORED_PATTERNS or name.endswith(".pyc") or "__pycache__" in path.parts:
        return True
    if name.startswith("state.db"):
        return True
    return False


def _is_secret(path: Path) -> bool:
    """Check if file is considered a secret/credential."""
    name = path.name
    if name in SECRET_PATTERNS or name.endswith(".key") or name.endswith(".token"):
        return True
    return False


@config_app.command("path")
def config_path() -> None:
    """Show the active CStation configuration directory."""
    console.print(f"CStation User Config: [bold cyan]{CSTATION_CONFIG_DIR}[/bold cyan]")
    if CSTATION_CONFIG_DIR.exists():
        console.print("  Status: [green]Exists[/green]")
    else:
        console.print("  Status: [red]Missing[/red]")


@config_app.command("export")
def config_export(
    out: Optional[Path] = typer.Option(
        None, "--out", "-o", help="Target archive path (default: ./cstation-config-YYYYMMDD_HHMMSS.tar.gz)"
    ),
    include_secrets: bool = typer.Option(
        True,
        "--include-secrets/--no-secrets",
        help="Include sensitive credentials (.env, tokens) in archive",
    ),
) -> None:
    """Export CStation configurations to a portable .tar.gz bundle."""
    source_dir = CSTATION_CONFIG_DIR
    if not source_dir.exists():
        console.print(f"[red]✗[/red] Configuration directory does not exist: {source_dir}")
        raise typer.Exit(1)

    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_path = out or Path(f"cstation-config-{now_str}.tar.gz")

    if dest_path.exists():
        console.print(f"[red]✗[/red] Destination archive already exists: {dest_path}")
        raise typer.Exit(1)

    exported_files: list[str] = []
    skipped_secrets: list[str] = []

    with tarfile.open(dest_path, "w:gz") as tar:
        for root, dirs, files in os.walk(source_dir):
            root_path = Path(root)
            for f in files:
                file_path = root_path / f
                if _is_ignored(file_path):
                    continue

                if not include_secrets and _is_secret(file_path):
                    skipped_secrets.append(file_path.name)
                    continue

                rel_path = file_path.relative_to(source_dir)
                tar.add(file_path, arcname=str(rel_path))
                exported_files.append(str(rel_path))

    size_kb = dest_path.stat().st_size / 1024
    console.print(f"\n[green]✓[/green] Successfully exported [bold]{len(exported_files)}[/bold] file(s) to [bold cyan]{dest_path}[/bold cyan] ({size_kb:.1f} KB)")

    if skipped_secrets:
        console.print(f"  [dim]Excluded {len(skipped_secrets)} secret(s): {', '.join(skipped_secrets)}[/dim]")

    record_audit(
        command="config export",
        target=str(dest_path),
        status="success",
        message=f"Exported {len(exported_files)} files (secrets={include_secrets})",
    )


@config_app.command("import")
def config_import(
    archive: Path = typer.Argument(..., help="Path to cstation-config archive (.tar.gz) to import"),
    dest: Optional[Path] = typer.Option(
        None, "--dest", "-d", help="Destination config directory (default: ~/.config/cstation)"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing configuration without confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview files to be imported without modifying disk"),
    validate: bool = typer.Option(True, "--validate/--no-validate", help="Run cstation lint after extraction"),
) -> None:
    """Import and restore CStation configuration from a .tar.gz bundle."""
    if not archive.exists() or not archive.is_file():
        console.print(f"[red]✗[/red] Archive not found: {archive}")
        raise typer.Exit(1)

    target_dir = dest or CSTATION_CONFIG_DIR

    try:
        with tarfile.open(archive, "r:gz") as tar:
            members = tar.getmembers()
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to read archive {archive}: {e}")
        raise typer.Exit(1)

    # Validate against directory traversal (ZipSlip)
    for m in members:
        if m.name.startswith("/") or ".." in Path(m.name).parts:
            console.print(f"[red]✗ Security Error:[/red] Archive contains illegal relative path: {m.name}")
            raise typer.Exit(1)

    if dry_run:
        console.print(f"\n[bold cyan]Dry-run: Previewing import from {archive} to {target_dir}[/bold cyan]")
        table = Table(title="Archive Contents", show_header=True)
        table.add_column("File Path")
        table.add_column("Size (Bytes)", justify="right")
        for m in members:
            table.add_row(m.name, str(m.size))
        console.print(table)
        console.print(f"\nTotal: {len(members)} items would be extracted.")
        return

    if target_dir.exists() and any(target_dir.iterdir()):
        if not force:
            confirm = typer.confirm(f"Target directory {target_dir} contains existing configuration. Overwrite?", default=False)
            if not confirm:
                console.print("[dim]Import aborted by user.[/dim]")
                raise typer.Exit(0)

        # Automatic backup snapshot before overwriting
        now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = target_dir.parent / f"{target_dir.name}.bak.{now_str}"
        try:
            shutil.copytree(target_dir, backup_path, ignore=shutil.ignore_patterns("state.db*"))
            console.print(f"  [dim]Created backup snapshot at {backup_path}[/dim]")
        except Exception as e:
            console.print(f"[yellow]⚠ Could not create safety backup:[/yellow] {e}")

    target_dir.mkdir(parents=True, exist_ok=True)

    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(path=target_dir)

    console.print(f"[green]✓[/green] Successfully imported [bold]{len(members)}[/bold] items into [bold cyan]{target_dir}[/bold cyan]")

    record_audit(
        command="config import",
        target=str(archive),
        status="success",
        message=f"Imported {len(members)} files to {target_dir}",
    )

    if validate:
        console.print("\n[bold]Running pre-flight validation on imported configuration...[/bold]")
        from cstation.commands.lint.main import run_lint_checks
        res = run_lint_checks()
        if res.get("passed"):
            console.print(f"[bold green]✓ Validation passed:[/bold green] {res.get('total_checks')} checks OK.")
        else:
            console.print(f"[bold yellow]⚠ Imported configuration has {res.get('error_count')} errors, {res.get('warning_count')} warnings.[/bold yellow]")


@config_app.callback()
def config_callback(ctx: typer.Context) -> None:
    """Manage CStation configuration: export, import, inspect."""
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
