"""
cstation hindsight command group.
Management, status, and backup workflows for self-hosted Hindsight memory service.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, List

import typer
from rich.console import Console
from rich.table import Table

from cstation.config import CSTATION_VPS_DIR
from cstation.commands.vps.main import _resolve_vps_dir, _load_vps_config, _ssh_from_config

console = Console()

hindsight_app = typer.Typer(
    name="hindsight",
    help="Hindsight memory service backup and inspection",
    invoke_without_command=True,
)

DEFAULT_BACKUP_DIRS = ["/root/backups", "/var/backups", "/var/lib/postgresql/backups"]
DEFAULT_LOCAL_DEST = Path.home() / ".hermes" / "backups" / "hindsight"


@hindsight_app.callback()
def hindsight_callback(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())


def _find_vps_dir(vps_name: str) -> Path:
    """Resolve VPS directory with prefix fallback (e.g. 'sg07' -> 'sg07.ansis.com.sg')."""
    p = Path(vps_name)
    if p.is_dir():
        return p
    direct = CSTATION_VPS_DIR / vps_name
    if direct.is_dir():
        return direct
    if CSTATION_VPS_DIR.exists():
        for d in CSTATION_VPS_DIR.iterdir():
            if d.is_dir() and (d.name == vps_name or d.name.startswith(f"{vps_name}.")):
                return d
    return _resolve_vps_dir(p)


@hindsight_app.command("backup")
def hindsight_backup(
    vps: str = typer.Argument(..., help="VPS name or directory (e.g. sg07 or sg07.ansis.com.sg)"),
    dest: Optional[Path] = typer.Option(
        None, "--dest", "-d", help="Local directory to store the backup dump (default: ~/.hermes/backups/hindsight)"
    ),
    dbname: str = typer.Option(
        "hindsight", "--dbname", help="Database name to back up"
    ),
    db_container: Optional[str] = typer.Option(
        None, "--db-container", help="PostgreSQL database container name (default: auto-detected or SG07_DB)"
    ),
    keep: Optional[int] = typer.Option(
        5, "--keep", "-k", help="Number of recent backups to retain locally (default: 5, 0 to disable pruning)"
    ),
    trigger_dump: bool = typer.Option(
        False, "--trigger-dump", "-t", help="Trigger a live pg_dump on the VPS immediately before pulling"
    ),
) -> None:
    """Download Hindsight database backup dump from remote VPS to the local machine."""
    vps_dir = _find_vps_dir(vps)
    vps_data = _load_vps_config(vps_dir)
    identity_name = vps_data.identity.name
    ssh = _ssh_from_config(vps_data)

    console.print(f"\n[bold]Hindsight Memory Backup: {identity_name}[/bold]\n")

    local_dest = dest or DEFAULT_LOCAL_DEST
    local_dest.mkdir(parents=True, exist_ok=True)

    backup_path = None

    if trigger_dump:
        target_db_container = db_container
        if not target_db_container:
            res = ssh.run("docker ps --format '{{.Names}}' | grep -E '(_DB$|postgres)' | head -1", hide=True)
            if res and getattr(res, "stdout", "").strip():
                target_db_container = res.stdout.strip()
            else:
                target_db_container = "SG07_DB"

        console.print(f"  [dim]Triggering live pg_dump for database '{dbname}' in container '{target_db_container}'...[/dim]")
        dump_cmd = (
            f"mkdir -p /root/backups && "
            f"docker exec {target_db_container} pg_dump -U hindsight -d {dbname} -Fc > /root/backups/hindsight_live_$(date +%Y%m%d_%H%M%S).dump"
        )
        run_res = ssh.run(dump_cmd, sudo=True, hide=False)
        if getattr(run_res, "exited", 0) != 0:
            console.print("[red]✗[/red] Live pg_dump failed on remote host")
            raise typer.Exit(1)

    for d in DEFAULT_BACKUP_DIRS:
        res = ssh.run(f"ls -1t {d}/hindsight_*.dump 2>/dev/null | head -1", hide=True)
        if res and getattr(res, "stdout", "").strip():
            backup_path = res.stdout.strip()
            break

    if not backup_path:
        console.print(f"[red]✗[/red] No Hindsight backup dumps found in {', '.join(DEFAULT_BACKUP_DIRS)} on {identity_name}")
        console.print("[dim]Hint: Run with --trigger-dump to generate a fresh dump now.[/dim]")
        raise typer.Exit(1)

    console.print(f"  [green]✓[/green] Found remote dump: {backup_path}")

    res_stat = ssh.run(f"stat -c \"%s\" {backup_path} 2>/dev/null || stat -f \"%z\" {backup_path} 2>/dev/null", hide=True)
    file_size = 0
    if res_stat and getattr(res_stat, "stdout", "").strip():
        try:
            file_size = int(res_stat.stdout.strip())
        except ValueError:
            pass

    size_str = f"{file_size / (1024 * 1024):.1f}MB" if file_size > 0 else "unknown size"
    console.print(f"  Remote size: {size_str}")

    backup_basename = backup_path.rsplit("/", 1)[-1]
    local_file = local_dest / backup_basename

    console.print(f"  [dim]Downloading to {local_dest}...[/dim]")
    try:
        ssh.get(backup_path, str(local_file))
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to download backup dump: {e}")
        raise typer.Exit(1)

    actual_size = local_file.stat().st_size if local_file.exists() else 0
    actual_str = f"{actual_size / (1024 * 1024):.1f}MB" if actual_size > 0 else size_str
    console.print(f"  [green]✓[/green] Successfully saved: [bold]{local_file}[/bold] ({actual_str})")

    if keep and keep > 0:
        local_dumps = sorted(local_dest.glob("hindsight_*.dump"), key=lambda f: f.stat().st_mtime, reverse=True)
        if len(local_dumps) > keep:
            to_prune = local_dumps[keep:]
            console.print(f"  [dim]Pruning {len(to_prune)} older local backup(s) (keeping {keep})...[/dim]")
            for old_file in to_prune:
                try:
                    old_file.unlink()
                except OSError:
                    pass


@hindsight_app.command("status")
def hindsight_status(
    vps: str = typer.Argument(..., help="VPS name or directory (e.g. sg07 or sg07.ansis.com.sg)"),
) -> None:
    """Inspect the running Hindsight container, API endpoints, and backup status on a VPS."""
    vps_dir = _find_vps_dir(vps)
    vps_data = _load_vps_config(vps_dir)
    identity_name = vps_data.identity.name
    ssh = _ssh_from_config(vps_data)

    console.print(f"\n[bold]Hindsight Status: {identity_name}[/bold]\n")

    res_ps = ssh.run("docker ps --filter 'ancestor=ghcr.io/vectorize-io/hindsight' --format '{{.Names}}|{{.Status}}|{{.Ports}}'", hide=True)
    container_info = res_ps.stdout.strip() if res_ps else ""

    res_bk = ssh.run("ls -lh /root/backups/hindsight_*.dump 2>/dev/null | tail -1", hide=True)
    backup_info = res_bk.stdout.strip() if res_bk else "None found"

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Property", style="dim")
    table.add_column("Value")

    table.add_row("VPS Host", identity_name)
    if container_info:
        parts = container_info.split("|", 2)
        table.add_row("Container", parts[0])
        table.add_row("Status", f"[green]{parts[1]}[/green]")
        if len(parts) > 2:
            table.add_row("Ports", parts[2])
    else:
        table.add_row("Container", "[yellow]Not detected or stopped[/yellow]")

    table.add_row("Latest Remote Backup", backup_info)
    console.print(table)
