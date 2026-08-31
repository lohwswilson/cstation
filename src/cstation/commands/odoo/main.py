from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console

from cstation.ssh import SSHManager
from cstation.config import get_vps_secrets, get_config
from cstation.models import VPSConfig, ContainerConfig
from cstation.commands.vps.main import _resolve_vps_dir, _load_vps_config, _ssh_from_config
from cstation.commands.pw.sync import PWSync

console = Console()

odoo_app = typer.Typer(
    name="odoo",
    help="Odoo database backup, restore, and source code sync",
    invoke_without_command=True,
)

BACKUP_DIRS = ["/var/lib/odoo/backups", "/var/lib/odoo/backup"]


@odoo_app.callback()
def odoo_callback(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())


@odoo_app.command("backup")
def odoo_backup(
    vps: str = typer.Argument(..., help="VPS name or directory path"),
    container: str = typer.Argument(..., help="Odoo container name"),
    dbname: str = typer.Argument(..., help="Database name to back up"),
) -> None:
    """Download the latest Odoo auto_backup zip from a remote container to the local machine."""
    vps_dir = _resolve_vps_dir(Path(vps))
    vps_data = _load_vps_config(vps_dir)
    identity_name = vps_data.identity.name
    ssh = _ssh_from_config(vps_data)

    console.print(f"\n[bold]Odoo Backup: {identity_name}[/bold]\n")

    backup_path = None
    for d in BACKUP_DIRS:
        for pattern in [f"{dbname}_*.zip", f"*_{dbname}.zip", f"*{dbname}*.zip", f"{dbname}*.zip"]:
            result = ssh.run(
                f"docker exec {container} sh -c 'ls -1t {d}/{pattern} 2>/dev/null | head -1'",
                hide=True,
            )
            if result and getattr(result, "stdout", "").strip():
                backup_path = result.stdout.strip()
                break
        if backup_path:
            break

    if not backup_path:
        # Check all recent zips and verify db_name in manifest.json
        for d in BACKUP_DIRS:
            result = ssh.run(
                f"docker exec {container} sh -c 'ls -1t {d}/*.zip 2>/dev/null | head -5'",
                hide=True,
            )
            if result and getattr(result, "stdout", "").strip():
                for candidate in result.stdout.strip().splitlines():
                    cand = candidate.strip()
                    if not cand:
                        continue
                    manifest_cmd = (
                        f"docker exec {container} python3 -c \""
                        f"import zipfile, json\n"
                        f"try:\n"
                        f"    zf = zipfile.ZipFile('{cand}')\n"
                        f"    m = json.loads(zf.read('manifest.json').decode())\n"
                        f"    print(m.get('db_name', ''))\n"
                        f"except Exception:\n"
                        f"    pass\""
                    )
                    man_res = ssh.run(manifest_cmd, hide=True)
                    if man_res and getattr(man_res, "stdout", "").strip().lower() == dbname.lower():
                        backup_path = cand
                        break
            if backup_path:
                break

    if not backup_path:
        console.print(f"[red]✗[/red] No backups found for database '{dbname}' in container '{container}'")
        console.print("[dim]Searched: " + ", ".join(BACKUP_DIRS) + "[/dim]")
        raise typer.Exit(1)

    console.print(f"  [green]✓[/green] Found backup: {backup_path}")

    result = ssh.run(
        f"docker exec {container} sh -c 'stat -c \"%s\" {backup_path} 2>/dev/null'",
        hide=True,
    )
    file_size = 0
    if result and getattr(result, "stdout", "").strip():
        try:
            file_size = int(result.stdout.strip())
        except ValueError:
            pass

    if file_size > 0:
        size_mb = file_size / (1024 * 1024)
        size_str = f"{size_mb:.1f}MB" if size_mb < 1024 else f"{size_mb / 1024:.1f}GB"
        console.print(f"  Size: {size_str}")
    else:
        size_str = "unknown size"

    backup_basename = backup_path.rsplit("/", 1)[-1]
    host_tmp = f"/tmp/{backup_basename}"
    console.print(f"  [dim]Copying from container to host...[/dim]")
    result = ssh.run(f"docker cp {container}:{backup_path} {host_tmp}", sudo=True)
    if not result or getattr(result, "exited", 1) != 0:
        console.print(f"[red]✗[/red] Failed to copy backup from container")
        raise typer.Exit(1)

    local_path = Path.cwd() / backup_basename
    console.print(f"  [dim]Downloading to local machine...[/dim]")
    try:
        ssh.get(host_tmp, str(local_path))
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to download backup: {e}")
        ssh.run(f"rm -f {host_tmp}", sudo=True)
        raise typer.Exit(1)

    ssh.run(f"rm -f {host_tmp}", sudo=True)

    actual_size = local_path.stat().st_size if local_path.exists() else 0
    if actual_size > 0:
        actual_mb = actual_size / (1024 * 1024)
        actual_str = f"{actual_mb:.1f}MB" if actual_mb < 1024 else f"{actual_mb / 1024:.1f}GB"
    else:
        actual_str = size_str

    console.print(f"  [green]✓[/green] Saved to: {local_path} ({actual_str})")


@odoo_app.command("restore")
def odoo_restore(
    vps: str = typer.Argument(..., help="Destination VPS name or directory path"),
    container: str = typer.Argument(..., help="Destination Odoo container name"),
    backup_file: str = typer.Argument(..., help="Local backup zip file path"),
    dest_db: Optional[str] = typer.Option(None, "--dest-db", "-d", help="Destination database name (defaults to source db name from manifest)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    """Restore an Odoo backup zip to a remote VPS."""
    local_path = Path(backup_file)
    if not local_path.exists():
        console.print(f"[red]✗[/red] Backup file not found: {local_path}")
        raise typer.Exit(1)

    try:
        with zipfile.ZipFile(str(local_path)) as zf:
            if "manifest.json" not in zf.namelist():
                console.print("[red]✗[/red] Invalid Odoo backup: manifest.json not found")
                raise typer.Exit(1)
            manifest = json.loads(zf.read("manifest.json"))
            if str(manifest.get("odoo_dump")) != "1":
                console.print("[red]✗[/red] Invalid Odoo backup: not an Odoo dump")
                raise typer.Exit(1)
            source_db = manifest.get("db_name", "unknown")
            odoo_version = manifest.get("version", "unknown")
    except zipfile.BadZipFile:
        console.print(f"[red]✗[/red] Not a valid zip file: {local_path}")
        raise typer.Exit(1)

    dest_dbname = dest_db or source_db

    vps_dir = _resolve_vps_dir(Path(vps))
    vps_data = _load_vps_config(vps_dir)
    identity_name = vps_data.identity.name
    ssh = _ssh_from_config(vps_data)

    frag_path = vps_dir / f"{container}.yaml"
    if not frag_path.exists():
        console.print(f"[red]✗[/red] Fragment not found: {frag_path}")
        raise typer.Exit(1)

    with frag_path.open("r", encoding="utf-8") as f:
        frag_dict = yaml.safe_load(f)

    from pydantic import ValidationError
    try:
        frag_config = ContainerConfig(**frag_dict)
    except ValidationError as e:
        console.print(f"[red]✗[/red] Fragment validation failed for {frag_path}:")
        for error in e.errors():
            loc = ".".join(str(l) for l in error["loc"])
            msg = error["msg"]
            console.print(f"  - [bold]{loc}[/bold]: {msg}")
        raise typer.Exit(6)

    db_container = frag_config.env.get("HOST")
    if not db_container:
        console.print("[red]✗[/red] Fragment missing env.HOST (database container)")
        raise typer.Exit(1)

    db_user = (frag_config.odoo_conf or {}).get("db_user") or frag_config.env.get("USER")
    owner = frag_config.owner or "100:101"

    secrets = get_vps_secrets(identity_name, container)
    db_password = secrets.get("PASSWORD") or frag_config.env.get("PASSWORD")

    data_volume = None
    for vol in frag_config.volumes:
        parts = vol.split(":")
        if len(parts) >= 2 and parts[1] == "/var/lib/odoo":
            data_volume = parts[0]
    if not data_volume:
        console.print("[red]✗[/red] Could not determine data volume path from fragment")
        raise typer.Exit(1)

    console.print(f"\n[bold]Odoo Restore: {identity_name}[/bold]\n")
    console.print(f"  Source database:  {source_db} (Odoo {odoo_version})")
    console.print(f"  Destination DB:   {dest_dbname}")
    console.print(f"  DB container:    {db_container}")
    console.print(f"  DB owner:        {db_user}")
    console.print(f"  Data volume:     {data_volume}")
    console.print(f"  Backup file:      {local_path.name}")
    console.print()

    if not yes:
        confirm = typer.confirm("Proceed with restore?", default=False)
        if not confirm:
            console.print("[dim]Aborted.[/dim]")
            raise typer.Exit(0)

    backup_filename = local_path.name
    host_tmp = f"/tmp/{backup_filename}"
    restore_dir = f"/tmp/{dest_dbname}_restore"
    filestore_dir = f"{data_volume}/filestore/{dest_dbname}"

    console.print(f"  [dim]Uploading backup to {ssh.host}...[/dim]")
    ssh.put(str(local_path), host_tmp)

    console.print(f"  [dim]Extracting backup on host...[/dim]")
    ssh.run(f"rm -rf {restore_dir}", sudo=True)
    ssh.run(f"mkdir -p {restore_dir}", sudo=True)
    ssh.run(
        f"python3 -c \"import zipfile; zipfile.ZipFile('{host_tmp}').extractall('{restore_dir}')\"",
        sudo=True,
    )
    ssh.run(f"rm -f {host_tmp}", sudo=True)

    console.print(f"  [dim]Creating database {dest_dbname}...[/dim]")
    check_sql = f"SELECT 1 FROM pg_database WHERE datname='{dest_dbname}'"
    check_result = ssh.run(
        f"docker exec {db_container} psql -U postgres -t -c \"{check_sql}\" 2>/dev/null",
        hide=True,
        sudo=True,
    )
    db_exists = "1" in (getattr(check_result, "stdout", "").strip() if check_result else "")

    if db_exists:
        console.print(f"  [yellow]⚠[/yellow] Database {dest_dbname} already exists. Dropping and recreating...")
        ssh.run(
            f"docker exec {db_container} psql -U postgres -c"
            f" \"REVOKE CONNECT ON DATABASE \\\"{dest_dbname}\\\" FROM PUBLIC;\" 2>/dev/null",
            sudo=True,
        )
        ssh.run(
            f"docker exec {db_container} psql -U postgres -c"
            f" \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = \\\"{dest_dbname}\\\";\" 2>/dev/null",
            sudo=True,
        )
        ssh.run(
            f"docker exec {db_container} psql -U postgres -c"
            f" \"DROP DATABASE \\\"{dest_dbname}\\\";\" 2>/dev/null",
            sudo=True,
        )

    ssh.run(
        f"docker exec {db_container} psql -U postgres -c"
        f" \"CREATE DATABASE \\\"{dest_dbname}\\\" OWNER \\\"{db_user}\\\";\"",
        sudo=True,
    )
    console.print(f"  [green]✓[/green] Created database {dest_dbname}")

    if db_password:
        escaped_password = db_password.replace("'", "''")
        check_user_sql = f"SELECT 1 FROM pg_roles WHERE rolname='{db_user}'"
        user_result = ssh.run(
            f"docker exec {db_container} psql -U postgres -t -c \"{check_user_sql}\" 2>/dev/null",
            hide=True,
            sudo=True,
        )
        user_exists = "1" in (getattr(user_result, "stdout", "").strip() if user_result else "")
        if not user_exists:
            ssh.run(
                f"docker exec {db_container} psql -U postgres -c"
                f" \"CREATE USER \\\"{db_user}\\\" WITH PASSWORD '{escaped_password}' SUPERUSER;\" 2>/dev/null",
                sudo=True,
            )
        else:
            ssh.run(
                f"docker exec {db_container} psql -U postgres -c"
                f" \"ALTER USER \\\"{db_user}\\\" WITH PASSWORD '{escaped_password}';\" 2>/dev/null",
                sudo=True,
            )

    console.print(f"  [dim]Restoring dump.sql into {dest_dbname}...[/dim]")
    dump_path = f"{restore_dir}/dump.sql"
    ssh.run(
        f"docker exec -i {db_container} psql -U postgres -d {dest_dbname}"
        f" < {dump_path}",
        sudo=True,
        hide=True,
    )
    console.print(f"  [green]✓[/green] Restored dump.sql into {dest_dbname}")

    console.print(f"  [dim]Reassigning table ownership to {db_user}...[/dim]")
    ssh.run(
        f"docker exec {db_container} psql -U postgres -d {dest_dbname}"
        f" -c \"REASSIGN OWNED BY CURRENT_USER TO \\\"{db_user}\\\";\"",
        sudo=True,
    )
    ssh.run(
        f"docker exec {db_container} psql -U postgres -d {dest_dbname}"
        f" -c \"GRANT ALL PRIVILEGES ON DATABASE \\\"{dest_dbname}\\\" TO \\\"{db_user}\\\";\"",
        sudo=True,
    )
    ssh.run(
        f"docker exec {db_container} psql -U postgres -d {dest_dbname}"
        f" -c \"GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO \\\"{db_user}\\\";\"",
        sudo=True,
    )
    ssh.run(
        f"docker exec {db_container} psql -U postgres -d {dest_dbname}"
        f" -c \"GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO \\\"{db_user}\\\";\"",
        sudo=True,
    )
    ssh.run(
        f"docker exec {db_container} psql -U postgres -d {dest_dbname}"
        f" -c \"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO \\\"{db_user}\\\";\"",
        sudo=True,
    )
    ssh.run(
        f"docker exec {db_container} psql -U postgres -d {dest_dbname}"
        f" -c \"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON SEQUENCES TO \\\"{db_user}\\\";\"",
        sudo=True,
    )
    console.print(f"  [green]✓[/green] Reassigned ownership to {db_user}")

    console.print(f"  [dim]Copying filestore...[/dim]")
    ssh.run(f"mkdir -p {filestore_dir}", sudo=True)
    source_filestore = f"{restore_dir}/filestore"
    ssh.run(f"cp -r {source_filestore}/* {filestore_dir}/", sudo=True)
    console.print(f"  [green]✓[/green] Copied filestore")

    console.print(f"  [dim]Creating checklist directory...[/dim]")
    ssh.run(f"mkdir -p {filestore_dir}/checklist", sudo=True)
    ssh.run(
        f"bash -c 'cd {filestore_dir}/checklist && for i in $(seq 0 255); do mkdir -p $(printf \"%02x\" $i); done'",
        sudo=True,
    )
    console.print(f"  [green]✓[/green] Created checklist directory (256 subdirs)")

    owner_parts = owner.split(":")
    ssh.run(f"chown -R {owner_parts[0]}:{owner_parts[1]} {filestore_dir}", sudo=True)
    console.print(f"  [green]✓[/green] Set filestore ownership to {owner}")

    console.print(f"  [dim]Cleaning up temp files...[/dim]")
    ssh.run(f"rm -rf {restore_dir}", sudo=True)

    compose_path = f"/var/lib/{container}/docker-compose.yml"
    console.print(f"  [dim]Restarting {container}...[/dim]")
    ssh.run(f"docker compose -f {compose_path} restart", sudo=True)
    console.print(f"  [green]✓[/green] Restarted {container}")

    console.print(f"\n[bold green]✓ Restore complete![/bold green]")
    console.print(f"  Database: {dest_dbname}")
    console.print(f"  Container: {container}")
    console.print(f"  VPS: {identity_name}")


@odoo_app.command("sync")
def odoo_sync(
    host: str = typer.Argument(..., help="Target hostname (e.g. sg06)"),
    version: str = typer.Argument(..., help="PW version (e.g. 3.0, 18.0)"),
    port: int = typer.Option(22, "--port", "-p", help="SSH port"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show what would be synced without executing"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
) -> None:
    """Sync Odoo PW source code and addons to a VPS for Docker container access."""
    config = get_config()
    pw_sync = PWSync(config, console)

    try:
        success = pw_sync.sync_files(
            host=host,
            version=version,
            port=port,
            dry_run=dry_run,
            verbose=verbose,
            exclude_cache=True,
            progress=None,
        )
        if success:
            console.print(f"[green]✓[/green] Synced PW.{version} and PW_ADDONS.{version} to {host}")
        else:
            console.print(f"[red]✗[/red] Sync failed for {host}")
            raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)