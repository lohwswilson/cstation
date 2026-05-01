#!/usr/bin/env python3
"""
Cloudflare DNS management commands for CStation CLI
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console
from rich.table import Table

from cstation.config import get_config
from cstation.commands.vps.main import _resolve_vps_dir, _CStationYamlDumper
from cstation.providers.cloudflare import CloudflareProvider, DNSRecord, DNSZone
from cstation.providers.errors import ProviderAuthError, ProviderError, ProviderNotFoundError

console = Console()

cloudflare_app = typer.Typer(
    name="cloudflare",
    help="Cloudflare DNS management",
    invoke_without_command=True,
)


def _load_dns_config(vps_dir: Path) -> dict:
    dns_yaml = vps_dir / "dns.yaml"
    if not dns_yaml.exists():
        console.print(f"[red]✗[/red] No dns.yaml found in {vps_dir}")
        console.print("[dim]Create dns.yaml with kind: DNS to manage DNS records.[/dim]")
        raise typer.Exit(6)
    with dns_yaml.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        console.print(f"[red]✗[/red] Invalid dns.yaml: expected mapping")
        raise typer.Exit(6)
    if data.get("kind") != "DNS":
        console.print(f"[red]✗[/red] Invalid dns.yaml: expected kind=DNS, got kind={data.get('kind')}")
        raise typer.Exit(6)
    return data


def _resolve_record_name(rec_name: str, domain: str) -> str:
    """Resolve a dns.yaml record name to a fully qualified domain name.

    dns.yaml uses Cloudflare convention:
    - name: ""    → domain root (e.g., "synercatalyst.com")
    - name: "mail" → subdomain (e.g., "mail.synercatalyst.com")
    - name: "mail.us02" → nested subdomain (e.g., "mail.us02.synercatalyst.com")
    """
    if not rec_name or rec_name == "@":
        return domain
    return f"{rec_name}.{domain}"


def _dns_records_from_config(data: dict) -> list[DNSRecord]:
    records = []
    for domain, domain_data in data.get("domains", {}).items():
        zone_id = ""
        if isinstance(domain_data, dict):
            zone_id = domain_data.get("zone_id", "") or ""
            domain_records = domain_data.get("records", [])
        else:
            continue
        for rec_data in domain_records:
            full_name = _resolve_record_name(rec_data.get("name", ""), domain)
            records.append(DNSRecord(
                domain=domain,
                name=full_name,
                type=rec_data.get("type", ""),
                content=rec_data.get("value", ""),
                ttl=rec_data.get("ttl", 1),
                priority=rec_data.get("priority"),
                proxied=rec_data.get("proxied", False),
                comment=rec_data.get("comment", "cstation"),
            ))
    return records


def _get_provider() -> CloudflareProvider:
    from cstation.commands.vps.main import _HttpClient
    config = get_config()
    config_data = config.config_data
    api_token = config_data.get("cloudflare", {}).get("api_token", "")
    if not api_token:
        console.print("[red]✗[/red] No Cloudflare API token configured.")
        console.print("[dim]Add to ~/.config/cstation/config.yaml:\n  cloudflare:\n    api_token: YOUR_TOKEN[/dim]")
        raise typer.Exit(2)
    return CloudflareProvider(api_token=api_token, http=_HttpClient())


def _fmt_record(rec: DNSRecord) -> str:
    name = rec.name if rec.name else "@"
    priority = f"  pri={rec.priority}" if rec.priority is not None and rec.type == "MX" else ""
    proxied = " (proxied)" if rec.proxied else ""
    ttl = "auto" if rec.ttl == 1 else str(rec.ttl)
    return f"{rec.type:6s} {name:40s} → {rec.content}{priority}  [dim](ttl={ttl}{proxied})[/dim]"


def _compute_drift(local_records: list[DNSRecord], remote_records: list[DNSRecord]) -> tuple[list[DNSRecord], list[tuple[DNSRecord, DNSRecord]], list[DNSRecord]]:
    to_create: list[DNSRecord] = []
    to_update: list[tuple[DNSRecord, DNSRecord]] = []
    to_delete: list[DNSRecord] = []

    remote_by_key: dict[str, DNSRecord] = {}
    for r in remote_records:
        key = (r.type, r.name.lower())
        remote_by_key.setdefault(key, r)

    local_by_key: dict[str, DNSRecord] = {}
    for r in local_records:
        key = (r.type, r.name.lower())
        local_by_key[key] = r

    for r in local_records:
        key = (r.type, r.name.lower())
        remote = remote_by_key.get(key)
        if remote is None:
            to_create.append(r)
        else:
            content_match = r.content.strip().strip('"') == remote.content.strip().strip('"')
            if not content_match or r.ttl != remote.ttl or r.proxied != remote.proxied or r.priority != remote.priority:
                to_update.append((r, remote))

    for r in remote_records:
        key = (r.type, r.name.lower())
        local = local_by_key.get(key)
        if local is None:
            to_delete.append(r)

    return to_create, to_update, to_delete


@cloudflare_app.command("zones")
def list_zones() -> None:
    """List all Cloudflare DNS zones."""
    provider = _get_provider()
    try:
        zones = provider.list_zones()
    except ProviderAuthError as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(2)
    except ProviderError as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(1)

    if not zones:
        console.print("[dim]No zones found.[/dim]")
        return

    table = Table(title="Cloudflare DNS Zones")
    table.add_column("Name", style="bold")
    table.add_column("Zone ID", style="dim")
    table.add_column("Status")
    for z in zones:
        table.add_row(z.name, z.id, z.status)
    console.print(table)


@cloudflare_app.command("plan")
def cloudflare_plan(
    vps: str = typer.Argument(..., help="VPS name or directory path"),
    domain: Optional[str] = typer.Option(None, "--domain", "-d", help="Filter to a specific domain"),
) -> None:
    """
    Dry-run: compare dns.yaml against Cloudflare and show drift.

    Reads dns.yaml from the VPS config directory and compares declared
    DNS records against what's currently in Cloudflare. Shows records
    to create and update. Unmanaged records in Cloudflare are shown
    as a count only (use --delete with apply to remove them).
    """
    vps_dir = _resolve_vps_dir(Path(vps))
    data = _load_dns_config(vps_dir)
    local_records = _dns_records_from_config(data)

    if domain:
        local_records = [r for r in local_records if r.domain == domain]

    if not local_records:
        console.print("[dim]No DNS records declared in dns.yaml.[/dim]")
        return

    provider = _get_provider()
    identity = _load_vps_config(vps_dir).get("identity", {}).get("name", vps_dir.name)
    console.print(f"\n[bold]Cloudflare DNS Plan: {identity}[/bold] [dim]({vps_dir}/dns.yaml)[/dim]\n")

    domains = sorted(set(r.domain for r in local_records))
    zone_cache: dict[str, str] = {}

    all_to_create: list[DNSRecord] = []
    all_to_update: list[tuple[DNSRecord, DNSRecord]] = []
    all_to_delete: list[DNSRecord] = []

    for d in domains:
        console.print(f"[bold]Domain: {d}[/bold]")
        try:
            if d not in zone_cache:
                zone_cache[d] = provider.get_zone_id(d)
            zone_id = zone_cache[d]
            remote_records = provider.list_records(zone_id, domain=d)
        except ProviderNotFoundError:
            console.print(f"  [yellow]⚠[/yellow] Zone not found for {d}, skipping")
            console.print()
            continue
        except (ProviderAuthError, ProviderError) as e:
            console.print(f"  [red]✗[/red] {e}")
            raise typer.Exit(1)

        domain_local = [r for r in local_records if r.domain == d]
        to_create, to_update, to_delete = _compute_drift(domain_local, remote_records)

        all_to_create.extend(to_create)
        all_to_update.extend(to_update)
        all_to_delete.extend(to_delete)

        if not to_create and not to_update and not to_delete:
            console.print("  [green]✓[/green] No changes needed")
            console.print()
            continue

        for r in to_create:
            console.print(f"  [green]+[/green] {_fmt_record(r)}")
        for local, remote in to_update:
            console.print(f"  [yellow]~[/yellow] {_fmt_record(local)}")
            console.print(f"       was: {remote.content}  (ttl={remote.ttl})")
        if to_delete:
            console.print(f"  [dim]({len(to_delete)} unmanaged records in Cloudflare — not shown)[/dim]")
        console.print()

    total_changes = len(all_to_create) + len(all_to_update)
    if total_changes == 0 and not all_to_delete:
        console.print("[green]✓[/green] All DNS records are up to date.")
    else:
        console.print(f"[bold]Summary:[/bold] {len(all_to_create)} to create, {len(all_to_update)} to update, {len(all_to_delete)} unmanaged in Cloudflare")
        console.print("[dim]Run 'cstation cloudflare apply <vps>' to create/update records.[/dim]")


@cloudflare_app.command("apply")
def cloudflare_apply(
    vps: str = typer.Argument(..., help="VPS name or directory path"),
    domain: Optional[str] = typer.Option(None, "--domain", "-d", help="Apply only for a specific domain"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    delete: bool = typer.Option(False, "--delete", help="Delete remote records not in dns.yaml"),
) -> None:
    """
    Apply DNS records from dns.yaml to Cloudflare.

    Creates missing records, updates changed records. By default does NOT
    delete records that exist in Cloudflare but not in dns.yaml (use --delete
    to enable deletions).
    """
    vps_dir = _resolve_vps_dir(Path(vps))
    data = _load_dns_config(vps_dir)
    local_records = _dns_records_from_config(data)

    if domain:
        local_records = [r for r in local_records if r.domain == domain]

    if not local_records:
        console.print("[dim]No DNS records declared in dns.yaml.[/dim]")
        return

    provider = _get_provider()
    identity = _load_vps_config(vps_dir).get("identity", {}).get("name", vps_dir.name)
    console.print(f"\n[bold]Cloudflare DNS Apply: {identity}[/bold] [dim]({vps_dir}/dns.yaml)[/dim]\n")

    domains = sorted(set(r.domain for r in local_records))
    zone_cache: dict[str, str] = {}

    all_to_create: list[DNSRecord] = []
    all_to_update: list[tuple[DNSRecord, DNSRecord]] = []
    all_to_delete: list[DNSRecord] = []

    for d in domains:
        try:
            if d not in zone_cache:
                zone_cache[d] = provider.get_zone_id(d)
            zone_id = zone_cache[d]
            remote_records = provider.list_records(zone_id, domain=d)
        except ProviderNotFoundError:
            console.print(f"[yellow]⚠[/yellow] Zone not found for {d}, skipping")
            continue
        except (ProviderAuthError, ProviderError) as e:
            console.print(f"[red]✗[/red] {e}")
            raise typer.Exit(1)

        domain_local = [r for r in local_records if r.domain == d]
        to_create, to_update, to_delete = _compute_drift(domain_local, remote_records)

        all_to_create.extend(to_create)
        all_to_update.extend(to_update)
        all_to_delete.extend(to_delete)

    if not all_to_create and not all_to_update and (not delete or not all_to_delete):
        console.print("[green]✓[/green] All DNS records are up to date.")
        return

    for r in all_to_create:
        console.print(f"  [green]+[/green] {_fmt_record(r)}")
    for local, remote in all_to_update:
        console.print(f"  [yellow]~[/yellow] {_fmt_record(local)}")
        console.print(f"       was: {remote.content}  (ttl={remote.ttl})")
    if delete and all_to_delete:
        for r in all_to_delete:
            console.print(f"  [red]-[/red] {_fmt_record(r)}")
    elif all_to_delete:
        console.print(f"\n  [dim]({len(all_to_delete)} unmanaged records in Cloudflare — use --delete to remove)[/dim]")

    total = len(all_to_create) + len(all_to_update) + (len(all_to_delete) if delete else 0)
    if not yes:
        confirm = typer.confirm(f"\nApply {total} change(s)?", default=False)
        if not confirm:
            console.print("[dim]Aborted.[/dim]")
            raise typer.Exit(0)
        console.print()

    for d in domains:
        if d not in zone_cache:
            continue
        zone_id = zone_cache[d]
        domain_local = [r for r in local_records if r.domain == d]
        domain_remote = provider.list_records(zone_id, domain=d)
        to_create, to_update, to_delete = _compute_drift(domain_local, domain_remote)

        for r in to_create:
            try:
                new_rec = provider.create_record(zone_id, r)
                console.print(f"  [green]✓[/green] Created {r.type} {r.name} → {r.content}")
            except ProviderError as e:
                console.print(f"  [red]✗[/red] Failed to create {r.type} {r.name}: {e}")

        for local, remote in to_update:
            try:
                local.id = remote.id
                updated = provider.update_record(zone_id, remote.id, local)
                console.print(f"  [green]✓[/green] Updated {local.type} {local.name} → {local.content}")
            except ProviderError as e:
                console.print(f"  [red]✗[/red] Failed to update {local.type} {local.name}: {e}")

        if delete:
            for r in to_delete:
                try:
                    provider.delete_record(zone_id, r.id)
                    console.print(f"  [green]✓[/green] Deleted {r.type} {r.name} → {r.content}")
                except ProviderError as e:
                    console.print(f"  [red]✗[/red] Failed to delete {r.type} {r.name}: {e}")

    console.print(f"\n[green]✓[/green] DNS apply complete for [bold]{identity}[/bold]")


def _load_vps_config(vps_dir: Path) -> dict:
    from cstation.commands.vps.main import _load_vps_config as _vps_load
    return _vps_load(vps_dir)


@cloudflare_app.callback()
def cloudflare_callback(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        from rich import print as rprint
        rprint(ctx.get_help())
        raise typer.Exit(0)