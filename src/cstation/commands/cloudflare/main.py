#!/usr/bin/env python3
"""
Cloudflare DNS management commands for CStation CLI

Supports two modes:
  1. Domain-based (recommended): reads from config/dns/<domain>.yaml
  2. VPS-based (legacy): reads from config/vps/<vps>/dns.yaml
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console
from rich.table import Table

from cstation.config import get_config
from cstation.providers.cloudflare import CloudflareProvider, DNSRecord, DNSZone
from cstation.providers.errors import ProviderAuthError, ProviderError, ProviderNotFoundError

console = Console()

cloudflare_app = typer.Typer(
    name="cloudflare",
    help="Cloudflare DNS management",
    invoke_without_command=True,
)

DNS_DIR = Path("config/dns")


def _load_domain_config(domain: str) -> dict:
    dns_file = DNS_DIR / f"{domain}.yaml"
    if not dns_file.exists():
        console.print(f"[red]✗[/red] No DNS config found for {domain}")
        console.print(f"[dim]Expected: {dns_file}[/dim]")
        console.print("[dim]Create it with kind: DNS and domain: <domain>[/dim]")
        raise typer.Exit(6)
    with dns_file.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        console.print(f"[red]✗[/red] Invalid {dns_file}: expected mapping")
        raise typer.Exit(6)
    if data.get("kind") != "DNS":
        console.print(f"[red]✗[/red] Invalid {dns_file}: expected kind=DNS, got kind={data.get('kind')}")
        raise typer.Exit(6)
    declared_domain = data.get("domain", "")
    if declared_domain and declared_domain != domain:
        console.print(f"[red]✗[/red] Domain mismatch: file declares '{declared_domain}' but expected '{domain}'")
        raise typer.Exit(6)
    return data


def _load_legacy_config(vps_dir: Path) -> dict:
    dns_yaml = vps_dir / "dns.yaml"
    if not dns_yaml.exists():
        return {}
    with dns_yaml.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict) or data.get("kind") != "DNS":
        return {}
    return data


def _list_available_domains() -> list[str]:
    domains = []
    if DNS_DIR.exists():
        for f in sorted(DNS_DIR.iterdir()):
            if f.suffix in (".yaml", ".yml") and f.is_file():
                domains.append(f.stem)
    return domains


def _resolve_record_name(rec_name: str, domain: str) -> str:
    if not rec_name or rec_name == "@":
        return domain
    return f"{rec_name}.{domain}"


def _dns_records_from_domain_config(data: dict) -> list[DNSRecord]:
    domain = data.get("domain", "")
    records = []
    for rec_data in data.get("records", []):
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
            srv_weight=rec_data.get("srv_weight"),
            srv_port=rec_data.get("srv_port"),
        ))
    return records


def _dns_records_from_legacy_config(data: dict) -> list[DNSRecord]:
    records = []
    for domain, domain_data in data.get("domains", {}).items():
        if not isinstance(domain_data, dict):
            continue
        domain_records = domain_data.get("records", [])
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
                srv_weight=rec_data.get("srv_weight"),
                srv_port=rec_data.get("srv_port"),
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
    priority = f"  pri={rec.priority}" if rec.priority is not None and rec.type in ("MX", "SRV") else ""
    srv_info = ""
    if rec.type == "SRV" and rec.srv_weight is not None and rec.srv_port is not None:
        srv_info = f"  w={rec.srv_weight} p={rec.srv_port}"
    proxied = " (proxied)" if rec.proxied else ""
    ttl = "auto" if rec.ttl == 1 else str(rec.ttl)
    return f"{rec.type:6s} {name:40s} → {rec.content}{priority}{srv_info}  [dim](ttl={ttl}{proxied})[/dim]"


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
            priority_match = (r.priority if r.priority is not None else 0) == (remote.priority if remote.priority is not None else 0)
            weight_match = (r.srv_weight if r.srv_weight is not None else 0) == (remote.srv_weight if remote.srv_weight is not None else 0)
            port_match = (r.srv_port if r.srv_port is not None else 0) == (remote.srv_port if remote.srv_port is not None else 0)
            if not content_match or r.ttl != remote.ttl or r.proxied != remote.proxied or not priority_match or not weight_match or not port_match:
                to_update.append((r, remote))

    for r in remote_records:
        key = (r.type, r.name.lower())
        local = local_by_key.get(key)
        if local is None:
            to_delete.append(r)

    return to_create, to_update, to_delete


def _collect_records(domains: list[str]) -> list[DNSRecord]:
    all_records: list[DNSRecord] = []
    for domain in domains:
        data = _load_domain_config(domain)
        records = _dns_records_from_domain_config(data)
        all_records.extend(records)
    return all_records


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
def cloudflarePlan(
    domains: Optional[list[str]] = typer.Argument(None, help="Domain(s) to plan. Defaults to all domains in config/dns/"),
) -> None:
    """
    Dry-run: compare DNS config against Cloudflare and show drift.

    Reads from config/dns/<domain>.yaml files. If no domains specified,
    plans all domains found in config/dns/.
    """
    if not domains:
        domains = _list_available_domains()
        if not domains:
            console.print("[dim]No domain config files found in config/dns/.[/dim]")
            return

    local_records = _collect_records(domains)
    if not local_records:
        console.print("[dim]No DNS records declared.[/dim]")
        return

    provider = _get_provider()
    console.print(f"\n[bold]Cloudflare DNS Plan[/bold] [dim](config/dns/)[/dim]\n")

    zone_cache: dict[str, str] = {}

    all_to_create: list[DNSRecord] = []
    all_to_update: list[tuple[DNSRecord, DNSRecord]] = []
    all_to_delete: list[DNSRecord] = []

    for d in sorted(domains):
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
        console.print("[dim]Run 'cstation cloudflare apply <domain>' to create/update records.[/dim]")


@cloudflare_app.command("apply")
def cloudflareApply(
    domains: Optional[list[str]] = typer.Argument(None, help="Domain(s) to apply. Defaults to all domains in config/dns/"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    delete: bool = typer.Option(False, "--delete", help="Delete remote records not in dns.yaml"),
) -> None:
    """
    Apply DNS records from config/dns/ to Cloudflare.

    Creates missing records, updates changed records. By default does NOT
    delete records that exist in Cloudflare but not in config (use --delete
    to enable deletions).
    """
    if not domains:
        domains = _list_available_domains()
        if not domains:
            console.print("[dim]No domain config files found in config/dns/.[/dim]")
            return

    local_records = _collect_records(domains)
    if not local_records:
        console.print("[dim]No DNS records declared.[/dim]")
        return

    provider = _get_provider()
    console.print(f"\n[bold]Cloudflare DNS Apply[/bold] [dim](config/dns/)[/dim]\n")

    zone_cache: dict[str, str] = {}

    all_to_create: list[DNSRecord] = []
    all_to_update: list[tuple[DNSRecord, DNSRecord]] = []
    all_to_delete: list[DNSRecord] = []

    for d in sorted(domains):
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
        domain_list = ", ".join(sorted(domains))
        confirm = typer.confirm(f"\nApply {total} change(s) for [{domain_list}]?", default=False)
        if not confirm:
            console.print("[dim]Aborted.[/dim]")
            raise typer.Exit(0)
        console.print()

    for d in sorted(domains):
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

    console.print(f"\n[green]✓[/green] DNS apply complete for [bold]{', '.join(sorted(domains))}[/bold]")


@cloudflare_app.callback()
def cloudflare_callback(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        from rich import print as rprint
        rprint(ctx.get_help())
        raise typer.Exit(0)